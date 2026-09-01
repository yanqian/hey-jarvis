"""Guided F060 diagnosis for Realtime near-end speech detection."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.evals.realtime_common import DEFAULT_EVIDENCE_ROOT, DEFAULT_FIXTURE_ROOT


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_PATH = DEFAULT_EVIDENCE_ROOT / "F060-diagnosis.json"
SAFE_EVENT_TYPES = frozenset(
    {
        "host_connected",
        "host_error",
        "host_input_level",
        "host_speech_started",
        "host_speech_stopped",
        "host_response_created",
        "host_response_done",
        "host_stopped",
        "wake_microphone_reopened",
    }
)
SAFE_REASONS = frozenset(
    {
        "cancelled",
        "completed",
        "explicit",
        "end_phrase",
        "idle_timeout",
        "max_duration",
        "error",
        "webrtc_negotiation_failed",
    }
)
SAFE_STATES = frozenset(
    {"wake_owned", "host_starting", "host_ready", "host_active", "host_stopping"}
)
LEVEL_PHASES = frozenset({"no_remote_playback", "remote_playback"})
MAX_LEVEL_EVENTS = 80
SAFE_DIAGNOSTIC_VALUE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
NEGOTIATION_DIAGNOSTIC_FIELDS = frozenset(
    {
        "errorType",
        "errorCode",
    }
)


class RealtimeDiagnosisError(RuntimeError):
    """Raised when the guided diagnostic cannot produce trustworthy evidence."""


class RealtimeDiagnosisLiveFailure(RealtimeDiagnosisError):
    """A live diagnostic failure carrying bounded sanitized evidence."""

    def __init__(self, message: str, evidence: dict[str, object]) -> None:
        super().__init__(message)
        self.evidence = evidence


def _json_request(url: str, *, method: str = "GET") -> dict[str, object]:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=3.0) as response:
        return json.loads(response.read())


def sanitize_diagnostic_report(report: dict[str, object]) -> dict[str, object]:
    safe_events: list[dict[str, object]] = []
    level_events = 0
    events = report.get("events")
    for event in events if isinstance(events, list) else []:
        if (
            not isinstance(event, dict)
            or event.get("type") not in SAFE_EVENT_TYPES
            or not isinstance(event.get("at_ms"), int)
        ):
            continue
        event_type = str(event["type"])
        safe: dict[str, object] = {"type": event_type, "at_ms": int(event["at_ms"])}
        if isinstance(event.get("session_id"), str):
            safe["session_id"] = str(event["session_id"])[:128]
        if event_type == "host_input_level":
            if level_events >= MAX_LEVEL_EVENTS:
                continue
            phase = event.get("phase")
            rms = event.get("rms")
            peak = event.get("peak")
            sample_count = event.get("sampleCount")
            if (
                phase not in LEVEL_PHASES
                or isinstance(rms, bool)
                or not isinstance(rms, (int, float))
                or isinstance(peak, bool)
                or not isinstance(peak, (int, float))
                or not 0.0 <= float(rms) <= 1.0
                or not 0.0 <= float(peak) <= 1.0
                or isinstance(sample_count, bool)
                or not isinstance(sample_count, int)
                or not 1 <= sample_count <= 10
            ):
                continue
            safe.update(
                {
                    "phase": phase,
                    "rms": round(float(rms), 4),
                    "peak": round(float(peak), 4),
                    "sampleCount": sample_count,
                }
            )
            level_events += 1
        if event_type == "host_error":
            for status_field in ("localHttpStatus", "upstreamHttpStatus"):
                http_status = event.get(status_field)
                if (
                    isinstance(http_status, bool)
                    or not isinstance(http_status, int)
                    or not 400 <= http_status <= 599
                ):
                    continue
                safe[status_field] = http_status
            for key in NEGOTIATION_DIAGNOSTIC_FIELDS:
                value = event.get(key)
                if isinstance(value, str) and SAFE_DIAGNOSTIC_VALUE.fullmatch(value):
                    safe[key] = value
        reason = event.get("reason")
        if isinstance(reason, str) and reason in SAFE_REASONS:
            safe["reason"] = reason
        elif "reason" in event:
            safe["reason"] = "redacted"
        safe_events.append(safe)
    state = report.get("state")
    return {
        "state": state if state in SAFE_STATES else "unknown",
        "wake_microphone_open": report.get("wake_microphone_open") is True,
        "events": safe_events[-200:],
    }


def _validated_level_events(
    report: dict[str, object], session_id: str
) -> list[dict[str, object]]:
    """Validate all level windows for summaries without expanding saved evidence."""
    validated: list[dict[str, object]] = []
    events = report.get("events")
    for event in events if isinstance(events, list) else []:
        if (
            not isinstance(event, dict)
            or event.get("type") != "host_input_level"
            or event.get("session_id") != session_id
            or not isinstance(event.get("at_ms"), int)
        ):
            continue
        phase = event.get("phase")
        rms = event.get("rms")
        peak = event.get("peak")
        sample_count = event.get("sampleCount")
        if (
            phase not in LEVEL_PHASES
            or isinstance(rms, bool)
            or not isinstance(rms, (int, float))
            or isinstance(peak, bool)
            or not isinstance(peak, (int, float))
            or not 0.0 <= float(rms) <= 1.0
            or not 0.0 <= float(peak) <= 1.0
            or isinstance(sample_count, bool)
            or not isinstance(sample_count, int)
            or not 1 <= sample_count <= 10
        ):
            continue
        validated.append(
            {
                "type": "host_input_level",
                "at_ms": int(event["at_ms"]),
                "session_id": session_id[:128],
                "phase": phase,
                "rms": round(float(rms), 4),
                "peak": round(float(peak), 4),
                "sampleCount": sample_count,
            }
        )
    return validated


def _level_summary(events: list[dict[str, object]]) -> dict[str, object]:
    if not events:
        return {"window_count": 0, "max_rms": 0.0, "max_peak": 0.0, "mean_rms": 0.0}
    rms_values = [float(event["rms"]) for event in events]
    return {
        "window_count": len(events),
        "max_rms": round(max(rms_values), 4),
        "max_peak": round(max(float(event["peak"]) for event in events), 4),
        "mean_rms": round(sum(rms_values) / len(rms_values), 4),
    }


def build_diagnostic_observation(
    *,
    report: dict[str, object],
    session_id: str,
    baseline_end_ms: int,
    no_playback_start_ms: int,
    remote_playback_start_ms: int,
) -> dict[str, object]:
    sanitized = sanitize_diagnostic_report(report)
    raw_events = report.get("events")
    events = [
        event
        for event in (raw_events if isinstance(raw_events, list) else [])
        if isinstance(event, dict)
        and event.get("session_id") == session_id
        and isinstance(event.get("at_ms"), int)
    ]
    level_events = _validated_level_events(report, session_id)
    baseline = [
        event
        for event in level_events
        if int(event["at_ms"]) <= baseline_end_ms
        and event.get("phase") == "no_remote_playback"
    ]
    no_playback = [
        event
        for event in level_events
        if no_playback_start_ms <= int(event["at_ms"]) < remote_playback_start_ms
        and event.get("phase") == "no_remote_playback"
    ]
    remote_playback = [
        event
        for event in level_events
        if int(event["at_ms"]) >= remote_playback_start_ms
        and event.get("phase") == "remote_playback"
    ]
    no_playback_vad = any(
        event.get("type") == "host_speech_started"
        and no_playback_start_ms <= int(event["at_ms"]) < remote_playback_start_ms
        for event in events
    )
    remote_playback_vad = any(
        event.get("type") == "host_speech_started"
        and int(event["at_ms"]) >= remote_playback_start_ms
        for event in events
    )
    return {
        "session_id": session_id,
        "markers": {
            "baseline_end_ms": baseline_end_ms,
            "no_playback_start_ms": no_playback_start_ms,
            "remote_playback_start_ms": remote_playback_start_ms,
        },
        "summaries": {
            "silence": _level_summary(baseline),
            "no_remote_playback_speech": _level_summary(no_playback),
            "remote_playback_speech": _level_summary(remote_playback),
        },
        "vad": {
            "no_remote_playback_speech_started": no_playback_vad,
            "remote_playback_speech_started": remote_playback_vad,
        },
        "cleanup": {
            "state": sanitized["state"],
            "wake_microphone_open": sanitized["wake_microphone_open"],
        },
        "report": sanitized,
    }


def classify_diagnostic_observation(observation: dict[str, object]) -> dict[str, object]:
    summaries = observation.get("summaries")
    vad = observation.get("vad")
    cleanup = observation.get("cleanup")
    if not isinstance(summaries, dict) or not isinstance(vad, dict) or not isinstance(cleanup, dict):
        raise RealtimeDiagnosisError("F060 observation is missing summaries, VAD, or cleanup")
    try:
        silence = summaries["silence"]
        no_playback = summaries["no_remote_playback_speech"]
        remote_playback = summaries["remote_playback_speech"]
        baseline_rms = float(silence["max_rms"])
        no_playback_rms = float(no_playback["max_rms"])
        remote_playback_rms = float(remote_playback["max_rms"])
        counts = (
            int(silence["window_count"]),
            int(no_playback["window_count"]),
            int(remote_playback["window_count"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RealtimeDiagnosisError("F060 observation summaries were malformed") from exc
    if any(count < 1 for count in counts):
        category = "inconclusive"
        no_playback_lift = False
        remote_playback_lift = False
    else:
        lift_threshold = max(0.005, baseline_rms * 2.5)
        no_playback_lift = no_playback_rms >= lift_threshold
        remote_playback_lift = remote_playback_rms >= lift_threshold
        no_playback_vad = vad.get("no_remote_playback_speech_started") is True
        remote_playback_vad = vad.get("remote_playback_speech_started") is True
        if not no_playback_lift and not remote_playback_lift:
            category = "capture_path"
        elif no_playback_lift and not no_playback_vad:
            category = "server_vad_sensitivity"
        elif no_playback_vad and not remote_playback_lift:
            category = "full_duplex_attenuation"
        elif no_playback_vad and remote_playback_lift and not remote_playback_vad:
            category = "server_vad_sensitivity"
        elif no_playback_vad and remote_playback_vad:
            category = "event_orchestration"
        else:
            category = "inconclusive"
    return {
        "result": "diagnosed",
        "category": category,
        "support": {
            "silence_max_rms": round(baseline_rms, 4),
            "no_remote_playback_max_rms": round(no_playback_rms, 4),
            "remote_playback_max_rms": round(remote_playback_rms, 4),
            "no_remote_playback_level_lift": no_playback_lift,
            "remote_playback_level_lift": remote_playback_lift,
            "no_remote_playback_speech_started": vad.get("no_remote_playback_speech_started")
            is True,
            "remote_playback_speech_started": vad.get("remote_playback_speech_started") is True,
            "window_counts": list(counts),
            "cleanup_restored": cleanup.get("state") == "wake_owned"
            and cleanup.get("wake_microphone_open") is True,
        },
        "interpretation": "diagnostic evidence only; no Realtime setting was changed and RT003 was not relabeled",
    }


class AssistedInputDiagnosisRunner:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8770",
        wake_fixture: Path | None = None,
        request: Callable[..., dict[str, object]] = _json_request,
        play: Callable[[Path], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        transition_timeout: float = 30.0,
        baseline_seconds: float = 1.2,
        speech_window_seconds: float = 3.0,
        announce: Callable[[str], None] = print,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.wake_fixture = wake_fixture or self._default_wake_fixture()
        self.request = request
        self.play = play or self._afplay
        self.clock = clock
        self.sleep = sleep
        self.transition_timeout = transition_timeout
        self.baseline_seconds = baseline_seconds
        self.speech_window_seconds = speech_window_seconds
        self.announce = announce

    def run(self) -> dict[str, object]:
        stage = "preconditions"
        session_id: str | None = None
        markers: dict[str, int] = {}
        try:
            initial = self._report()
            if initial.get("state") != "wake_owned" or initial.get("wake_microphone_open") is not True:
                raise RealtimeDiagnosisError(
                    "F060 requires an armed host in wake_owned with the wake microphone open"
                )
            if not self.wake_fixture.exists():
                raise RealtimeDiagnosisError(f"F060 wake fixture is missing: {self.wake_fixture}")
            initial_event_ms = max(
                (
                    int(event["at_ms"])
                    for event in initial.get("events", [])
                    if isinstance(event, dict) and isinstance(event.get("at_ms"), int)
                ),
                default=-1,
            )
            stage = "diagnostic_enable"
            self.request(
                f"{self.base_url}/api/input-level-diagnostics",
                method="POST",
            )
            stage = "session_start"
            self.play(self.wake_fixture)
            active = self._wait(
                lambda report: report.get("state") == "host_active",
                "host_active",
                abort_error_after_ms=initial_event_ms,
            )
            connected = self._latest_event(active, "host_connected")
            session_id = connected.get("session_id") if connected else None
            if not isinstance(session_id, str) or not session_id:
                raise RealtimeDiagnosisError("F060 active host exposed no sanitized session identity")

            stage = "silence_baseline"
            self.announce("F060: remain quiet briefly while the microphone baseline is measured.")
            baseline_report = self._collect_for(self.baseline_seconds, session_id)
            baseline_levels = self._session_events(
                baseline_report, "host_input_level", session_id, phase="no_remote_playback"
            )
            if not baseline_levels:
                raise RealtimeDiagnosisError("F060 observed no browser input-level baseline windows")
            markers["baseline_end_ms"] = int(baseline_levels[-1]["at_ms"])

            stage = "no_remote_playback_speech"
            markers["no_playback_start_ms"] = markers["baseline_end_ms"] + 1
            self.announce(
                "F060: with no answer playing, speak one normal sentence near the microphone now."
            )
            no_playback_report = self._collect_for(self.speech_window_seconds, session_id)
            response_created = self._first_session_event(
                no_playback_report,
                "host_response_created",
                session_id,
                at_or_after=markers["no_playback_start_ms"],
            )
            if response_created is not None:
                self._wait(
                    lambda report: self._first_session_event(
                        report,
                        "host_response_done",
                        session_id,
                        at_or_after=int(response_created["at_ms"]),
                    )
                    is not None,
                    "no-playback response.done",
                    abort_session_id=session_id,
                )

            stage = "remote_playback_speech"
            before_long = self._report()
            created_count = len(self._session_events(before_long, "host_response_created", session_id))
            self.request(f"{self.base_url}/api/long-answer", method="POST")
            long_report = self._wait(
                lambda report: len(
                    self._session_events(report, "host_response_created", session_id)
                )
                >= created_count + 1,
                "long-answer response.created",
                abort_session_id=session_id,
            )
            created = self._session_events(long_report, "host_response_created", session_id)
            markers["remote_playback_start_ms"] = int(created[created_count]["at_ms"])
            self.announce(
                "F060: while the counting answer is audible, speak one normal interruption now."
            )
            self._collect_for(self.speech_window_seconds, session_id)

            stage = "cleanup"
            self.request(f"{self.base_url}/api/stop", method="POST")
            final = self._wait(
                lambda report: report.get("state") == "wake_owned"
                and report.get("wake_microphone_open") is True,
                "fresh wake ownership",
            )
            observation = build_diagnostic_observation(
                report=final,
                session_id=session_id,
                baseline_end_ms=markers["baseline_end_ms"],
                no_playback_start_ms=markers["no_playback_start_ms"],
                remote_playback_start_ms=markers["remote_playback_start_ms"],
            )
            result = classify_diagnostic_observation(observation)
            return self._evidence(result=result, observation=observation)
        except Exception as exc:
            try:
                self.request(f"{self.base_url}/api/stop", method="POST")
            except Exception:
                pass
            try:
                report = self._report()
            except Exception:
                report = {"state": "unknown", "wake_microphone_open": False, "events": []}
            evidence = {
                "schema_version": 1,
                "feature_id": "F060",
                "evidence_tier": "live_near_end_diagnostic",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "result": {
                    "result": "failed",
                    "failure_stage": stage,
                    "failure_reason": self._safe_failure_message(exc),
                },
                "observation": {
                    "session_id": session_id,
                    "markers": markers,
                    "report": sanitize_diagnostic_report(report),
                },
                "privacy": "bounded normalized level summaries and allowlisted lifecycle metadata only",
            }
            raise RealtimeDiagnosisLiveFailure(self._safe_failure_message(exc), evidence) from exc

    def _report(self) -> dict[str, object]:
        return self.request(f"{self.base_url}/api/report")

    def _collect_for(self, seconds: float, session_id: str) -> dict[str, object]:
        deadline = self.clock() + seconds
        report = self._report()
        while self.clock() < deadline:
            report = self._report()
            if report.get("state") == "wake_owned":
                raise RealtimeDiagnosisError(
                    f"F060 session {session_id[:8]} closed during guided collection"
                )
            self.sleep(min(0.1, max(0.0, deadline - self.clock())))
        return report

    def _wait(
        self,
        predicate: Callable[[dict[str, object]], bool],
        label: str,
        *,
        abort_session_id: str | None = None,
        abort_error_after_ms: int | None = None,
    ) -> dict[str, object]:
        deadline = self.clock() + self.transition_timeout
        while self.clock() < deadline:
            report = self._report()
            if predicate(report):
                return report
            if abort_error_after_ms is not None:
                events = report.get("events")
                if any(
                    isinstance(event, dict)
                    and event.get("type") == "host_error"
                    and isinstance(event.get("at_ms"), int)
                    and int(event["at_ms"]) > abort_error_after_ms
                    for event in (events if isinstance(events, list) else [])
                ):
                    raise RealtimeDiagnosisError(
                        f"F060 host reported an error before {label}"
                    )
            if abort_session_id is not None and report.get("state") == "wake_owned":
                raise RealtimeDiagnosisError(
                    f"F060 session {abort_session_id[:8]} closed before {label}"
                )
            self.sleep(0.1)
        raise RealtimeDiagnosisError(f"F060 timed out waiting for {label}")

    @staticmethod
    def _session_events(
        report: dict[str, object],
        event_type: str,
        session_id: str,
        *,
        phase: str | None = None,
    ) -> list[dict[str, object]]:
        events = report.get("events")
        return [
            event
            for event in (events if isinstance(events, list) else [])
            if isinstance(event, dict)
            if event.get("type") == event_type
            and event.get("session_id") == session_id
            and (phase is None or event.get("phase") == phase)
        ]

    @staticmethod
    def _latest_event(
        report: dict[str, object], event_type: str
    ) -> dict[str, object] | None:
        events = report.get("events")
        for event in reversed(events if isinstance(events, list) else []):
            if isinstance(event, dict) and event.get("type") == event_type:
                return event
        return None

    @staticmethod
    def _first_session_event(
        report: dict[str, object],
        event_type: str,
        session_id: str,
        *,
        at_or_after: int,
    ) -> dict[str, object] | None:
        events = report.get("events")
        for event in events if isinstance(events, list) else []:
            if (
                isinstance(event, dict)
                and event.get("type") == event_type
                and event.get("session_id") == session_id
                and isinstance(event.get("at_ms"), int)
                and int(event["at_ms"]) >= at_or_after
            ):
                return event
        return None

    @staticmethod
    def _safe_failure_message(exc: Exception) -> str:
        if isinstance(exc, RealtimeDiagnosisError):
            return str(exc)[:240]
        return f"F060 live dependency failed: {type(exc).__name__}"

    @staticmethod
    def _afplay(path: Path) -> None:
        subprocess.run(["afplay", str(path)], check=True)

    @staticmethod
    def _default_wake_fixture() -> Path:
        return DEFAULT_FIXTURE_ROOT / "wake.wav"

    @staticmethod
    def _evidence(
        *,
        result: dict[str, object],
        observation: dict[str, object],
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "feature_id": "F060",
            "evidence_tier": "live_near_end_diagnostic",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "observation": observation,
            "privacy": "bounded normalized level summaries and allowlisted lifecycle metadata only",
        }


def write_evidence(path: Path, evidence: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _positive_seconds(value: str) -> float:
    seconds = float(value)
    if not 0.0 < seconds <= 60.0:
        raise argparse.ArgumentTypeError("duration must be greater than 0 and at most 60 seconds")
    return seconds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.realtime_input_diagnosis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    offline = subparsers.add_parser("offline", help="classify a sanitized F060 observation")
    offline.add_argument("observation", type=Path)
    live = subparsers.add_parser("live", help="run the guided live F060 diagnosis")
    live.add_argument("--base-url", default="http://127.0.0.1:8770")
    live.add_argument("--timeout", type=float, default=30.0)
    live.add_argument("--wake-fixture", type=Path)
    live.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    live.add_argument("--baseline-seconds", type=_positive_seconds, default=1.2)
    live.add_argument("--speech-window-seconds", type=_positive_seconds, default=3.0)
    args = parser.parse_args(argv)
    try:
        if args.command == "offline":
            payload = json.loads(args.observation.read_text(encoding="utf-8"))
            observation = payload.get("observation", payload) if isinstance(payload, dict) else payload
            if not isinstance(observation, dict):
                raise RealtimeDiagnosisError("F060 offline observation must be an object")
            print(json.dumps(classify_diagnostic_observation(observation), sort_keys=True))
            return 0
        runner = AssistedInputDiagnosisRunner(
            base_url=args.base_url,
            wake_fixture=args.wake_fixture,
            transition_timeout=args.timeout,
            baseline_seconds=args.baseline_seconds,
            speech_window_seconds=args.speech_window_seconds,
        )
        evidence = runner.run()
        write_evidence(args.evidence_output, evidence)
        print(json.dumps(evidence["result"], sort_keys=True))
        print(f"Saved sanitized F060 evidence to {args.evidence_output}")
        return 0
    except RealtimeDiagnosisLiveFailure as exc:
        write_evidence(args.evidence_output, exc.evidence)
        print(f"F060 diagnosis failed: {exc}")
        print(f"Saved sanitized F060 failure evidence to {args.evidence_output}")
        return 1
    except (RealtimeDiagnosisError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"F060 diagnosis failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

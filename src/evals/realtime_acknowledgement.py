"""Privacy-safe local versus Realtime acknowledgement comparison."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.evals.realtime_common import (
    PROJECT_ROOT,
    RealtimeRunFailure,
    RealtimeRunnerBase,
    RealtimeScenarioError,
    sanitize_report,
)


DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "tmp" / "realtime-evals" / "ACK-AB-evidence.json"
MODES = ("local", "realtime")
VERDICTS = frozenset({"local", "realtime", "no_difference", "inconclusive"})
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
FORBIDDEN_KEYS = frozenset(
    {"audio", "transcript", "response_text", "api_key", "token", "sdp", "ice", "provider_payload", "tool_data"}
)


def _reject_private_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise RealtimeScenarioError("ACK A/B observation contains a forbidden private field")
            _reject_private_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_private_keys(nested)


def _event(events: list[object], event_type: str) -> dict[str, object]:
    matches = [event for event in events if isinstance(event, dict) and event.get("type") == event_type]
    if len(matches) != 1:
        raise RealtimeScenarioError(f"ACK A/B trial requires exactly one {event_type}")
    return matches[0]


def _elapsed(start: dict[str, object], end: dict[str, object], label: str) -> int:
    start_ms, end_ms = start.get("at_ms"), end.get("at_ms")
    if (
        isinstance(start_ms, bool)
        or isinstance(end_ms, bool)
        or not isinstance(start_ms, int)
        or not isinstance(end_ms, int)
    ):
        raise RealtimeScenarioError(f"ACK A/B {label} timing was missing")
    value = end_ms - start_ms
    if not 0 <= value <= 60_000:
        raise RealtimeScenarioError(f"ACK A/B {label} timing was invalid")
    return value


def _trial_timing(trial: dict[str, object]) -> dict[str, object]:
    mode = trial.get("mode")
    events = trial.get("events")
    if mode not in MODES or not isinstance(events, list):
        raise RealtimeScenarioError("ACK A/B trial mode or events were invalid")
    wake = _event(events, "wake_confirmed")
    configured = _event(events, "host_session_configured")
    connected = _event(events, "host_connected")
    stopped = _event(events, "host_stopped")
    reopened = _event(events, "wake_microphone_reopened")
    timing: dict[str, object] = {
        "playback_path": "local_asset_player" if mode == "local" else "remote_webrtc_audio",
        "configured_session_ready_ms": _elapsed(wake, configured, "configured-session readiness"),
        "input_ready_ms": _elapsed(wake, connected, "input readiness"),
        "cleanup_ms": _elapsed(stopped, reopened, "cleanup"),
        "acoustic_onset_observable": False,
    }
    if mode == "local":
        started = _event(events, "ack_started")
        completed = _event(events, "ack_completed")
        duration = started.get("ack_asset_duration_ms")
        if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 60_000:
            raise RealtimeScenarioError("ACK A/B local trial requires a valid asset duration")
        timing.update(
            {
                "response_creation_ms": None,
                "first_observable_playback_ms": _elapsed(wake, started, "local playback start"),
                "playback_completion_ms": _elapsed(wake, completed, "local playback completion"),
                "ack_asset_duration_ms": duration,
            }
        )
        if not int(configured["at_ms"]) <= int(started["at_ms"]) <= int(completed["at_ms"]) <= int(connected["at_ms"]):
            raise RealtimeScenarioError("ACK A/B local lifecycle was misordered")
    else:
        created = _event(events, "host_realtime_ack_response_created")
        playback_started = _event(events, "host_realtime_ack_playback_started")
        response_done = _event(events, "host_realtime_ack_response_done")
        playback_stopped = _event(events, "host_realtime_ack_playback_stopped")
        if response_done.get("reason") != "completed":
            raise RealtimeScenarioError("ACK A/B Realtime response did not complete")
        if not (
            int(configured["at_ms"]) <= int(created["at_ms"])
            and int(created["at_ms"]) <= int(playback_started["at_ms"]) <= int(playback_stopped["at_ms"])
            and int(created["at_ms"]) <= int(response_done["at_ms"]) <= int(connected["at_ms"])
            and int(playback_stopped["at_ms"]) <= int(connected["at_ms"])
        ):
            raise RealtimeScenarioError("ACK A/B Realtime lifecycle was misordered")
        timing.update(
            {
                "response_creation_ms": _elapsed(wake, created, "Realtime response creation"),
                "first_observable_playback_ms": _elapsed(wake, playback_started, "Realtime playback start"),
                "playback_completion_ms": _elapsed(wake, playback_stopped, "Realtime playback completion"),
                "ack_asset_duration_ms": None,
            }
        )
    return timing


def evaluate_observation(observation: dict[str, object]) -> dict[str, object]:
    _reject_private_keys(observation)
    if set(observation) != {"configuration", "trials", "perceptual_verdict"}:
        raise RealtimeScenarioError("ACK A/B observation fields were invalid")
    configuration = observation.get("configuration")
    if not isinstance(configuration, dict) or set(configuration) != {"model", "voice", "output_volume", "host"}:
        raise RealtimeScenarioError("ACK A/B configuration was invalid")
    if any(not isinstance(configuration.get(key), str) or not SAFE_IDENTIFIER.fullmatch(str(configuration[key])) for key in ("model", "voice")):
        raise RealtimeScenarioError("ACK A/B model or voice identifier was invalid")
    volume = configuration.get("output_volume")
    if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not 0 <= float(volume) <= 1:
        raise RealtimeScenarioError("ACK A/B output volume was invalid")
    if configuration.get("host") != "same_loopback_host":
        raise RealtimeScenarioError("ACK A/B trials must use the same loopback host")
    trials = observation.get("trials")
    if not isinstance(trials, list) or [trial.get("mode") for trial in trials if isinstance(trial, dict)] != list(MODES):
        raise RealtimeScenarioError("ACK A/B requires one ordered local and Realtime trial")
    timings = {str(trial["mode"]): _trial_timing(trial) for trial in trials if isinstance(trial, dict)}
    verdict = observation.get("perceptual_verdict")
    if verdict not in VERDICTS:
        raise RealtimeScenarioError("ACK A/B perceptual verdict was invalid")
    if verdict == "realtime":
        recommendation = "consider_realtime_for_voice_consistency"
    elif verdict == "local":
        recommendation = "retain_local"
    else:
        recommendation = "inconclusive"
    return {
        "result": "passed",
        "timing_ms": timings,
        "input_ready_delta_ms": int(timings["realtime"]["input_ready_ms"]) - int(timings["local"]["input_ready_ms"]),
        "perceptual_verdict": verdict,
        "recommendation": recommendation,
        "latency_slo_claimed": False,
        "acoustic_onset_note": "Browser playback start is observable; physical acoustic onset is not measured.",
    }


class AcknowledgementABRunner(RealtimeRunnerBase):
    def __init__(
        self,
        *,
        manual_wake_provider: Callable[[str], None] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.manual_wake_provider = manual_wake_provider

    def run(
        self,
        *,
        verdict: str | None = None,
        verdict_provider: Callable[[], str] | None = None,
        reuse_latest_local: bool = False,
        local_trial: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            settings = self.request(f"{self.base_url}/api/realtime-settings")
            if local_trial is not None and reuse_latest_local:
                raise RealtimeScenarioError(
                    "ACK A/B local trial file cannot be combined with latest-host reuse"
                )
            if local_trial is not None:
                _reject_private_keys(local_trial)
                _trial_timing(local_trial)
                selected_local_trial = local_trial
            elif reuse_latest_local:
                selected_local_trial = self._latest_complete_local_trial(self.report())
            else:
                selected_local_trial = self._run_trial("local")
            trials = [selected_local_trial, self._run_trial("realtime")]
            selected_verdict = verdict or (verdict_provider() if verdict_provider else "inconclusive")
            if selected_verdict not in VERDICTS:
                raise RealtimeScenarioError("ACK A/B perceptual verdict was invalid")
            observation = {
                "configuration": {
                    "model": settings.get("model"),
                    "voice": settings.get("voice"),
                    "output_volume": settings.get("output_volume"),
                    "host": "same_loopback_host",
                },
                "trials": trials,
                "perceptual_verdict": selected_verdict,
            }
            result = evaluate_observation(observation)
            return self._evidence(observation, result)
        except (Exception, KeyboardInterrupt) as exc:
            try:
                self.stop()
            except Exception:
                pass
            evidence = self._evidence(
                {"configuration": {}, "trials": [], "perceptual_verdict": "inconclusive"},
                {"result": "failed", "failure_reason": self._safe_failure(exc)},
            )
            raise RealtimeRunFailure(self._safe_failure(exc), evidence) from exc

    def _run_trial(self, mode: str) -> dict[str, object]:
        initial = self.report()
        if initial.get("state") != "wake_owned" or initial.get("wake_microphone_open") is not True:
            raise RealtimeScenarioError("ACK A/B requires wake_owned before each trial")
        if self.manual_wake_provider is None and not self.wake_fixture.exists():
            raise RealtimeScenarioError("ACK A/B wake fixture is missing")
        initial_events = initial.get("events")
        initial_count = len(initial_events) if isinstance(initial_events, list) else 0
        if mode == "realtime":
            self.request(f"{self.base_url}/api/acknowledgement-experiment", method="POST")
        if self.manual_wake_provider is None:
            self.play(self.wake_fixture)
        else:
            self.manual_wake_provider(mode)
        self.wait(
            lambda report: report.get("state") == "host_active" and report.get("wake_microphone_open") is False,
            f"{mode} input readiness",
        )
        self.stop()
        final = self.wait(
            lambda report: report.get("state") == "wake_owned" and report.get("wake_microphone_open") is True,
            f"{mode} wake recovery",
        )
        raw_events = final.get("events")
        segment = raw_events[initial_count:] if isinstance(raw_events, list) else []
        return self._sanitize_trial(mode, segment, final)

    @staticmethod
    def _sanitize_trial(
        mode: str,
        segment: list[object],
        final: dict[str, object],
    ) -> dict[str, object]:
        safe = sanitize_report({"state": final.get("state"), "wake_microphone_open": final.get("wake_microphone_open"), "events": segment})
        events_without_session_ids = [
            {key: value for key, value in event.items() if key != "session_id"}
            for event in safe["events"]
        ]
        return {"mode": mode, "events": events_without_session_ids}

    @classmethod
    def _latest_complete_local_trial(cls, report: dict[str, object]) -> dict[str, object]:
        events = report.get("events")
        if not isinstance(events, list):
            raise RealtimeScenarioError("ACK A/B report has no reusable local trial")
        wake_positions = [
            index
            for index, event in enumerate(events)
            if isinstance(event, dict) and event.get("type") == "wake_confirmed"
        ]
        for offset, start in reversed(list(enumerate(wake_positions))):
            end = wake_positions[offset + 1] if offset + 1 < len(wake_positions) else len(events)
            segment = events[start:end]
            types = {event.get("type") for event in segment if isinstance(event, dict)}
            if {
                "ack_started",
                "ack_completed",
                "host_connected",
                "host_stopped",
                "wake_microphone_reopened",
            }.issubset(types) and "host_realtime_ack_response_created" not in types:
                trial = cls._sanitize_trial("local", segment, report)
                _trial_timing(trial)
                return trial
        raise RealtimeScenarioError("ACK A/B report has no complete reusable local trial")

    @staticmethod
    def _safe_failure(exc: Exception) -> str:
        return str(exc)[:240] if isinstance(exc, RealtimeScenarioError) else f"ACK A/B live dependency failed: {type(exc).__name__}"

    @staticmethod
    def _evidence(observation: dict[str, object], result: dict[str, object]) -> dict[str, object]:
        return {
            "schema_version": 1,
            "experiment_id": "ACK-AB",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "observation": observation,
            "privacy": "bounded configuration identifiers and sanitized lifecycle timings only",
        }


def write_evidence(path: Path, evidence: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None, *, input_fn: Callable[[str], str] = input) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.realtime_acknowledgement")
    commands = parser.add_subparsers(dest="command", required=True)
    offline = commands.add_parser("offline", help="evaluate a saved sanitized ACK A/B observation")
    offline.add_argument("observation", type=Path)
    live = commands.add_parser("live", help="run two audible trials against an armed local host")
    live.add_argument("--base-url", default="http://127.0.0.1:8770")
    live.add_argument("--timeout", type=float, default=30.0)
    live.add_argument("--wake-fixture", type=Path)
    live.add_argument(
        "--manual-wake",
        action="store_true",
        help="wait for an operator-triggered spoken wake before each trial",
    )
    live.add_argument(
        "--reuse-latest-local",
        action="store_true",
        help="reuse the latest complete sanitized local trial and run only Realtime",
    )
    live.add_argument(
        "--local-trial",
        type=Path,
        help="reuse a saved sanitized local trial and run only Realtime",
    )
    live.add_argument("--verdict", choices=sorted(VERDICTS))
    live.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    args = parser.parse_args(argv)
    try:
        if args.command == "offline":
            observation = json.loads(args.observation.read_text(encoding="utf-8"))
            print(json.dumps(evaluate_observation(observation), sort_keys=True))
            return 0
        runner = AcknowledgementABRunner(
            scenario_id="ACK-AB",
            base_url=args.base_url,
            wake_fixture=args.wake_fixture,
            transition_timeout=args.timeout,
            manual_wake_provider=(
                lambda mode: input_fn(
                    f"Press Enter, then say Hey Jarvis for the {mode} ACK trial: "
                )
                if args.manual_wake
                else None
            ),
        )
        saved_local_trial = (
            json.loads(args.local_trial.read_text(encoding="utf-8"))
            if args.local_trial is not None
            else None
        )
        evidence = runner.run(
            verdict=args.verdict,
            verdict_provider=lambda: input_fn(
                "After hearing local then Realtime ACK, choose local/realtime/no_difference/inconclusive: "
            ).strip(),
            reuse_latest_local=args.reuse_latest_local,
            local_trial=saved_local_trial,
        )
        write_evidence(args.evidence_output, evidence)
        print(json.dumps(evidence["result"], sort_keys=True))
        print(f"Saved sanitized ACK A/B evidence to {args.evidence_output}")
        return 0
    except RealtimeRunFailure as exc:
        write_evidence(args.evidence_output, exc.evidence)
        print(f"ACK A/B evaluation failed: {exc}")
        return 1
    except (RealtimeScenarioError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ACK A/B evaluation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

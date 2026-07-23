"""Spec-driven RT003 Realtime barge-in evaluation."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO_PATH = PROJECT_ROOT / "evals" / "realtime" / "scenarios" / "RT003.json"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "evals" / "realtime" / "scenario.schema.json"
DEFAULT_FIXTURE_ROOT = PROJECT_ROOT / "tmp" / "realtime-fixtures"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "tmp" / "realtime-evals" / "RT003-evidence.json"
SAFE_EVENT_FIELDS = frozenset({"type", "at_ms", "session_id", "reason"})
SAFE_EVENT_TYPES = frozenset(
    {
        "host_connected",
        "host_response_created",
        "host_speech_started",
        "host_speech_stopped",
        "host_response_done",
        "host_stopped",
        "wake_microphone_reopened",
    }
)
SAFE_EVENT_REASONS = frozenset(
    {
        "cancelled",
        "completed",
        "explicit",
        "end_phrase",
        "idle_timeout",
        "max_duration",
        "error",
        "test",
    }
)
SAFE_REPORT_STATES = frozenset({"wake_owned", "python_stopping", "host_starting", "host_active", "host_stopping"})


class RealtimeEvalError(RuntimeError):
    """Raised when the RT003 contract or observed behavior is invalid."""


class RealtimeLiveFailure(RealtimeEvalError):
    """A live RT003 failure that carries bounded sanitized evidence."""

    def __init__(self, message: str, evidence: dict[str, object]) -> None:
        super().__init__(message)
        self.evidence = evidence


def load_scenario(path: Path = DEFAULT_SCENARIO_PATH) -> dict[str, object]:
    try:
        scenario = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealtimeEvalError(f"RT003 scenario could not be loaded: {exc}") from exc
    validate_scenario(scenario)
    return scenario


def validate_scenario(
    scenario: dict[str, object],
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealtimeEvalError(f"Realtime scenario schema could not be loaded: {exc}") from exc

    missing = [field for field in schema["required"] if field not in scenario]
    if missing:
        raise RealtimeEvalError(f"RT003 scenario is missing required fields: {', '.join(missing)}")
    if scenario.get("id") != "RT003" or scenario.get("schema_version") != 1:
        raise RealtimeEvalError("RT003 scenario must use id RT003 and schema_version 1")
    if not isinstance(scenario.get("version"), int) or int(scenario["version"]) < 1:
        raise RealtimeEvalError("RT003 scenario version must be a positive integer")

    oracles = scenario.get("oracles")
    if not isinstance(oracles, dict):
        raise RealtimeEvalError("RT003 oracles must be an object")
    missing_oracles = [field for field in schema["oracle_required"] if field not in oracles]
    if missing_oracles:
        raise RealtimeEvalError(f"RT003 scenario is missing oracles: {', '.join(missing_oracles)}")
    latency_max = oracles.get("cancellation_latency_ms_max")
    if not isinstance(latency_max, int) or latency_max <= 0:
        raise RealtimeEvalError("RT003 cancellation latency threshold must be a positive integer")

    actions = scenario.get("human_actions")
    if (
        not isinstance(actions, list)
        or len(actions) != 1
        or not isinstance(actions[0], dict)
        or actions[0].get("source") != "live_near_end"
        or actions[0].get("count") != 1
    ):
        raise RealtimeEvalError("RT003 must require exactly one live_near_end human action")

    evidence = scenario.get("evidence")
    required_tiers = evidence.get("required") if isinstance(evidence, dict) else None
    if required_tiers != schema["evidence_tiers"]:
        raise RealtimeEvalError("RT003 must require offline and live_near_end evidence")

    privacy = scenario.get("privacy")
    if not isinstance(privacy, dict):
        raise RealtimeEvalError("RT003 privacy rules must be an object")
    if privacy.get("commit_audio") is not False or privacy.get("commit_transcript") is not False:
        raise RealtimeEvalError("RT003 must prohibit committed audio and transcripts")
    allowed = privacy.get("allowed_event_fields")
    if not isinstance(allowed, list) or set(allowed) - SAFE_EVENT_FIELDS:
        raise RealtimeEvalError("RT003 allowed event fields exceed the evaluator allowlist")
    forbidden = privacy.get("forbidden_fields")
    if not isinstance(forbidden, list) or not {"audio", "transcript", "api_key", "token"}.issubset(forbidden):
        raise RealtimeEvalError("RT003 privacy rules do not forbid required sensitive fields")


def sanitize_report(report: dict[str, object]) -> dict[str, object]:
    events = report.get("events")
    safe_events: list[dict[str, object]] = []
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        if event.get("type") not in SAFE_EVENT_TYPES or not isinstance(event.get("at_ms"), int):
            continue
        safe_event: dict[str, object] = {
            "type": event["type"],
            "at_ms": int(event["at_ms"]),
        }
        if isinstance(event.get("session_id"), str):
            safe_event["session_id"] = str(event["session_id"])[:128]
        reason = event.get("reason")
        if isinstance(reason, str) and reason in SAFE_EVENT_REASONS:
            safe_event["reason"] = reason
        elif "reason" in event:
            safe_event["reason"] = "redacted"
        safe_events.append(safe_event)
    state = report.get("state")
    return {
        "state": state if state in SAFE_REPORT_STATES else "unknown",
        "wake_microphone_open": report.get("wake_microphone_open") is True,
        "events": safe_events[-200:],
    }


def build_observation(
    *,
    report: dict[str, object],
    session_id: str,
    long_response_created_at_ms: int,
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "long_response_created_at_ms": long_response_created_at_ms,
        "report": sanitize_report(report),
    }


def evaluate_observation(
    scenario: dict[str, object],
    observation: dict[str, object],
) -> dict[str, object]:
    validate_scenario(scenario)
    session_id = observation.get("session_id")
    long_started = observation.get("long_response_created_at_ms")
    report = observation.get("report")
    if not isinstance(session_id, str) or not session_id:
        raise RealtimeEvalError("RT003 observation is missing a session identity")
    if not isinstance(long_started, int) or long_started < 0:
        raise RealtimeEvalError("RT003 observation has an invalid long-answer start time")
    if not isinstance(report, dict):
        raise RealtimeEvalError("RT003 observation is missing a sanitized report")

    events = report.get("events")
    if not isinstance(events, list):
        raise RealtimeEvalError("RT003 sanitized report has no event list")
    session_events = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("session_id") == session_id
        and isinstance(event.get("at_ms"), int)
        and int(event["at_ms"]) >= long_started
    ]
    long_event = _first_event(session_events, "host_response_created", at_or_after=long_started)
    if long_event is None or int(long_event["at_ms"]) != long_started:
        raise RealtimeEvalError("RT003 long-answer response.created marker is missing or stale")

    speech = _first_event(session_events, "host_speech_started", at_or_after=long_started)
    if speech is None:
        raise RealtimeEvalError("RT003 did not observe near-end host_speech_started for the active session")
    old_done = _first_event(session_events, "host_response_done", at_or_after=long_started)
    if old_done is None:
        raise RealtimeEvalError("RT003 did not observe the old response ending")
    latency_ms = int(old_done["at_ms"]) - int(speech["at_ms"])
    if latency_ms < 0:
        raise RealtimeEvalError("RT003 cancellation latency was negative; event ordering is invalid")

    oracles = scenario["oracles"]
    if old_done.get("reason") != oracles["old_response_reason"]:
        raise RealtimeEvalError(
            f"RT003 old response ended as {old_done.get('reason')!r}, "
            f"expected {oracles['old_response_reason']!r}"
        )
    if latency_ms > int(oracles["cancellation_latency_ms_max"]):
        raise RealtimeEvalError(
            f"RT003 cancellation latency {latency_ms}ms exceeded "
            f"{oracles['cancellation_latency_ms_max']}ms"
        )

    continuation_created = _first_event(
        session_events,
        "host_response_created",
        after=int(old_done["at_ms"]),
    )
    if continuation_created is None:
        raise RealtimeEvalError("RT003 did not observe a continuation response.created")
    continuation_done = _first_event(
        session_events,
        "host_response_done",
        at_or_after=int(continuation_created["at_ms"]),
    )
    if continuation_done is None or continuation_done.get("reason") != oracles["continuation_reason"]:
        actual = None if continuation_done is None else continuation_done.get("reason")
        raise RealtimeEvalError(
            f"RT003 continuation ended as {actual!r}, expected {oracles['continuation_reason']!r}"
        )
    if (
        report.get("state") != oracles["final_state"]
        or report.get("wake_microphone_open") is not oracles["wake_microphone_open"]
    ):
        raise RealtimeEvalError("RT003 cleanup did not restore wake_owned with the wake microphone open")

    return {
        "result": "passed",
        "cancellation_latency_ms": latency_ms,
        "old_response_reason": old_done.get("reason"),
        "continuation_reason": continuation_done.get("reason"),
        "recovered_to_wake": True,
    }


def _first_event(
    events: list[dict[str, object]],
    event_type: str,
    *,
    at_or_after: int | None = None,
    after: int | None = None,
) -> dict[str, object] | None:
    for event in events:
        at_ms = int(event["at_ms"])
        if event.get("type") != event_type:
            continue
        if at_or_after is not None and at_ms < at_or_after:
            continue
        if after is not None and at_ms <= after:
            continue
        return event
    return None


def _json_request(url: str, *, method: str = "GET") -> dict[str, object]:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=3.0) as response:
        return json.loads(response.read())


class AssistedBargeInRunner:
    def __init__(
        self,
        *,
        scenario: dict[str, object],
        base_url: str = "http://127.0.0.1:8770",
        wake_fixture: Path | None = None,
        request: Callable[..., dict[str, object]] = _json_request,
        play: Callable[[Path], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        transition_timeout: float = 30.0,
        announce: Callable[[str], None] = print,
    ) -> None:
        validate_scenario(scenario)
        self.scenario = scenario
        self.base_url = base_url.rstrip("/")
        self.wake_fixture = wake_fixture or self._default_wake_fixture()
        self.request = request
        self.play = play or self._afplay
        self.clock = clock
        self.sleep = sleep
        self.transition_timeout = transition_timeout
        self.announce = announce

    def run(self) -> dict[str, object]:
        stage = "preconditions"
        session_id: str | None = None
        long_started: int | None = None
        try:
            initial = self._report()
            if initial.get("state") != "wake_owned" or initial.get("wake_microphone_open") is not True:
                raise RealtimeEvalError(
                    "RT003 requires an armed host in wake_owned with the wake microphone open"
                )
            if not self.wake_fixture.exists():
                raise RealtimeEvalError(f"RT003 wake fixture is missing: {self.wake_fixture}")

            stage = "session_start"
            self.play(self.wake_fixture)
            active = self._wait(
                lambda report: report.get("state") == "host_active",
                "Realtime host_active after wake",
            )
            connected = self._latest_event(active, "host_connected")
            session_id = connected.get("session_id") if connected else None
            if not isinstance(session_id, str) or not session_id:
                raise RealtimeEvalError("RT003 active host did not expose a sanitized session identity")

            stage = "long_answer"
            created_count = self._event_count(active, "host_response_created", session_id)
            self.announce(
                "RT003: a long answer will start now. When it is audible, "
                "speak one natural interruption utterance near the microphone."
            )
            self.request(f"{self.base_url}/api/long-answer", method="POST")
            long_report = self._wait(
                lambda report: self._event_count(report, "host_response_created", session_id)
                >= created_count + 1,
                "long-answer response.created",
            )
            created_events = self._session_events(long_report, "host_response_created", session_id)
            long_created = created_events[created_count] if len(created_events) > created_count else None
            if long_created is None:
                raise RealtimeEvalError("RT003 could not identify the long-answer response.created")
            long_started = int(long_created["at_ms"])

            stage = "near_end_speech"
            interrupted = self._wait(
                lambda report: self._first_session_event(
                    report,
                    "host_response_done",
                    session_id,
                    at_or_after=long_started,
                )
                is not None,
                "human interruption response.done",
                abort_session_id=session_id,
            )
            old_done = self._first_session_event(
                interrupted,
                "host_response_done",
                session_id,
                at_or_after=long_started,
            )
            if old_done is None:
                raise RealtimeEvalError("RT003 did not observe the old response ending")
            stage = "continuation"
            continuation_report = self._wait(
                lambda report: self._completed_continuation(
                    report,
                    session_id,
                    after_ms=int(old_done["at_ms"]),
                ),
                "barge-in continuation response.done",
                abort_session_id=session_id,
            )
            stage = "cleanup"
            self.request(f"{self.base_url}/api/stop", method="POST")
            final = self._wait(
                lambda report: report.get("state") == "wake_owned"
                and report.get("wake_microphone_open") is True,
                "fresh wake ownership after stop",
            )
            observation = build_observation(
                report=final,
                session_id=session_id,
                long_response_created_at_ms=long_started,
            )
            result = evaluate_observation(self.scenario, observation)
            return self._evidence(observation, result)
        except Exception as exc:
            try:
                self.request(f"{self.base_url}/api/stop", method="POST")
            except Exception:
                pass
            try:
                final = self._report()
            except Exception:
                final = {"state": "unknown", "wake_microphone_open": False, "events": []}
            evidence = self._failure_evidence(
                stage=stage,
                failure=exc,
                report=final,
                session_id=session_id,
                long_started=long_started,
            )
            raise RealtimeLiveFailure(self._safe_failure_message(exc), evidence) from exc

    def _report(self) -> dict[str, object]:
        return self.request(f"{self.base_url}/api/report")

    def _wait(
        self,
        predicate: Callable[[dict[str, object]], bool],
        label: str,
        *,
        abort_session_id: str | None = None,
    ) -> dict[str, object]:
        deadline = self.clock() + self.transition_timeout
        while self.clock() < deadline:
            report = self._report()
            if predicate(report):
                return report
            if abort_session_id is not None and report.get("state") == "wake_owned":
                raise RealtimeEvalError(
                    f"RT003 session {abort_session_id[:8]} closed before {label}"
                )
            self.sleep(0.1)
        raise RealtimeEvalError(f"RT003 timed out waiting for {label}")

    @staticmethod
    def _event_count(report: dict[str, object], event_type: str, session_id: str) -> int:
        return len(AssistedBargeInRunner._session_events(report, event_type, session_id))

    @staticmethod
    def _session_events(
        report: dict[str, object],
        event_type: str,
        session_id: str,
    ) -> list[dict[str, object]]:
        events = report.get("events")
        if not isinstance(events, list):
            return []
        return [
            event
            for event in events
            if isinstance(event, dict)
            and event.get("type") == event_type
            and event.get("session_id") == session_id
        ]

    @staticmethod
    def _latest_event(
        report: dict[str, object],
        event_type: str,
        *,
        session_id: str | None = None,
    ) -> dict[str, object] | None:
        events = report.get("events")
        for event in reversed(events if isinstance(events, list) else []):
            if not isinstance(event, dict) or event.get("type") != event_type:
                continue
            if session_id is None or event.get("session_id") == session_id:
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

    @classmethod
    def _completed_continuation(
        cls,
        report: dict[str, object],
        session_id: str,
        *,
        after_ms: int,
    ) -> bool:
        created = cls._first_session_event(
            report,
            "host_response_created",
            session_id,
            at_or_after=after_ms + 1,
        )
        if created is None:
            return False
        done = cls._first_session_event(
            report,
            "host_response_done",
            session_id,
            at_or_after=int(created["at_ms"]),
        )
        return done is not None and done.get("reason") == "completed"

    def _evidence(
        self,
        observation: dict[str, object],
        result: dict[str, object],
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "scenario_id": self.scenario["id"],
            "scenario_version": self.scenario["version"],
            "evidence_tier": "live_near_end",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "observation": observation,
            "privacy": "allowlisted sanitized lifecycle metadata only",
        }

    def _failure_evidence(
        self,
        *,
        stage: str,
        failure: Exception,
        report: dict[str, object],
        session_id: str | None,
        long_started: int | None,
    ) -> dict[str, object]:
        observation: dict[str, object] = {"report": sanitize_report(report)}
        if session_id:
            observation["session_id"] = session_id
        if long_started is not None:
            observation["long_response_created_at_ms"] = long_started
        return {
            "schema_version": 1,
            "scenario_id": self.scenario["id"],
            "scenario_version": self.scenario["version"],
            "evidence_tier": "live_near_end",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": {
                "result": "failed",
                "failure_stage": stage,
                "failure_reason": self._safe_failure_message(failure),
            },
            "observation": observation,
            "privacy": "allowlisted sanitized lifecycle metadata only",
        }

    @staticmethod
    def _safe_failure_message(failure: Exception) -> str:
        if isinstance(failure, RealtimeEvalError):
            return str(failure)[:240]
        return f"RT003 live dependency failed: {type(failure).__name__}"

    @staticmethod
    def _afplay(path: Path) -> None:
        subprocess.run(["afplay", str(path)], check=True)

    @staticmethod
    def _default_wake_fixture() -> Path:
        replay = DEFAULT_FIXTURE_ROOT / "replay" / "wake.wav"
        return replay if replay.exists() else DEFAULT_FIXTURE_ROOT / "wake.wav"


def write_evidence(path: Path, evidence: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.realtime_barge_in")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)
    offline = subparsers.add_parser("offline", help="evaluate a saved sanitized RT003 observation")
    offline.add_argument("observation", type=Path)
    live = subparsers.add_parser("live", help="run the guided live-near-end RT003 evaluation")
    live.add_argument("--base-url", default="http://127.0.0.1:8770")
    live.add_argument("--timeout", type=float, default=30.0)
    live.add_argument("--wake-fixture", type=Path)
    live.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    args = parser.parse_args(argv)

    try:
        scenario = load_scenario(args.scenario)
        if args.command == "offline":
            observation = json.loads(args.observation.read_text(encoding="utf-8"))
            result = evaluate_observation(scenario, observation)
            print(json.dumps(result, sort_keys=True))
            return 0

        runner = AssistedBargeInRunner(
            scenario=scenario,
            base_url=args.base_url,
            wake_fixture=args.wake_fixture,
            transition_timeout=args.timeout,
        )
        evidence = runner.run()
        write_evidence(args.evidence_output, evidence)
        print(json.dumps(evidence["result"], sort_keys=True))
        print(f"Saved sanitized RT003 evidence to {args.evidence_output}")
        return 0
    except RealtimeLiveFailure as exc:
        write_evidence(args.evidence_output, exc.evidence)
        print(f"RT003 evaluation failed: {exc}")
        print(f"Saved sanitized RT003 failure evidence to {args.evidence_output}")
        return 1
    except (RealtimeEvalError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"RT003 evaluation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Automatic RT004 close, media cleanup, and distinct next-wake evaluation."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.evals.realtime_common import (
    AUDIO_ANALYSIS_TIMING_FIELDS,
    DEFAULT_EVIDENCE_ROOT,
    PROJECT_ROOT,
    RealtimeRunFailure,
    RealtimeRunnerBase,
    RealtimeScenarioError,
    sanitize_report,
    validate_handoff_timing_event,
    validate_scenario_contract,
)


DEFAULT_SCENARIO_PATH = PROJECT_ROOT / "evals/realtime/scenarios/RT004.json"
DEFAULT_EVIDENCE_PATH = DEFAULT_EVIDENCE_ROOT / "RT004-evidence.json"
CYCLE_TYPES = (
    "wake_microphone_closed",
    "host_microphone_requested",
    "host_microphone_acquired",
    "host_handoff_timing",
    "host_connected",
    "host_stopped",
    "wake_microphone_reopened",
)


def load_scenario(path: Path = DEFAULT_SCENARIO_PATH) -> dict[str, object]:
    try:
        scenario = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealtimeScenarioError(f"RT004 scenario could not be loaded: {exc}") from exc
    if not isinstance(scenario, dict):
        raise RealtimeScenarioError("RT004 scenario must be an object")
    validate_scenario(scenario)
    return scenario


def validate_scenario(scenario: dict[str, object]) -> None:
    validate_scenario_contract(scenario, expected_id="RT004")
    expected = {
        "session_count": 2,
        "distinct_session_ids": True,
        "media_stop_before_wake_reopen": True,
        "final_state": "wake_owned",
        "wake_microphone_open": True,
    }
    if scenario.get("oracles") != expected:
        raise RealtimeScenarioError("RT004 two-session cleanup oracles must remain fail-closed")


def build_observation(
    *,
    session_ids: tuple[str, str],
    active_a: dict[str, object],
    between: dict[str, object],
    active_b: dict[str, object],
    final: dict[str, object],
    initial_event_count: int = 0,
) -> dict[str, object]:
    def snapshot(report: dict[str, object]) -> dict[str, object]:
        raw = dict(report)
        events = report.get("events")
        raw["events"] = events[initial_event_count:] if isinstance(events, list) else []
        return sanitize_report(raw)

    return {
        "session_ids": list(session_ids),
        "active_a": snapshot(active_a),
        "between": snapshot(between),
        "active_b": snapshot(active_b),
        "final": snapshot(final),
    }


def evaluate_observation(
    scenario: dict[str, object],
    observation: dict[str, object],
) -> dict[str, object]:
    validate_scenario(scenario)
    session_ids = observation.get("session_ids")
    if (
        not isinstance(session_ids, list)
        or len(session_ids) != 2
        or not all(isinstance(value, str) and value for value in session_ids)
    ):
        raise RealtimeScenarioError("RT004 observation requires two session identities")
    session_a, session_b = session_ids
    if session_a == session_b:
        raise RealtimeScenarioError("RT004 next wake reused the first session identity")

    snapshots = {
        name: observation.get(name)
        for name in ("active_a", "between", "active_b", "final")
    }
    if not all(isinstance(value, dict) for value in snapshots.values()):
        raise RealtimeScenarioError("RT004 observation is missing lifecycle snapshots")
    active_a = snapshots["active_a"]
    between = snapshots["between"]
    active_b = snapshots["active_b"]
    final = snapshots["final"]
    assert isinstance(active_a, dict)
    assert isinstance(between, dict)
    assert isinstance(active_b, dict)
    assert isinstance(final, dict)

    for label, active in (("session A", active_a), ("session B", active_b)):
        if active.get("state") != "host_active" or active.get("wake_microphone_open") is not False:
            raise RealtimeScenarioError(
                f"RT004 {label} snapshot did not hold exclusive browser microphone ownership"
            )
    for label, recovered in (("first cleanup", between), ("final cleanup", final)):
        if (
            recovered.get("state") != "wake_owned"
            or recovered.get("wake_microphone_open") is not True
        ):
            raise RealtimeScenarioError(f"RT004 {label} did not restore wake ownership")

    expected_a = _expected_cycle(session_a)
    expected_b = _expected_cycle(session_b)
    _require_exact_prefix(active_a, expected_a[:5], "session A active")
    _require_exact_prefix(between, expected_a, "first cleanup")
    _require_exact_prefix(active_b, (*expected_a, *expected_b[:5]), "session B active")
    _require_exact_prefix(final, (*expected_a, *expected_b), "final cleanup")
    final_events = final.get("events")
    assert isinstance(final_events, list)
    timing_a = _session_timing(final_events, session_a)
    timing_b = _session_timing(final_events, session_b)
    return {
        "result": "passed",
        "session_count": 2,
        "distinct_session_ids": True,
        "media_cleanup_cycles": 2,
        "recovered_to_wake": True,
        "timing_ms": {
            "session_a": timing_a,
            "session_b": timing_b,
            "audio_analysis_first_minus_second_ms": (
                timing_a["audio_analysis_setup_ms"]
                - timing_b["audio_analysis_setup_ms"]
            ),
            "web_audio_subphases": sorted(AUDIO_ANALYSIS_TIMING_FIELDS),
        },
    }


def _expected_cycle(session_id: str) -> tuple[tuple[str, str | None], ...]:
    return tuple(
        (event_type, None if event_type == "wake_microphone_closed" else session_id)
        for event_type in CYCLE_TYPES
    )


def _session_timing(events: list[object], session_id: str) -> dict[str, int]:
    matches = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("type") == "host_handoff_timing"
        and event.get("session_id") == session_id
    ]
    if len(matches) != 1:
        raise RealtimeScenarioError(
            "RT004 requires exactly one handoff timing report for each session"
        )
    return validate_handoff_timing_event(matches[0], context="RT004")


def _require_exact_prefix(
    report: dict[str, object],
    expected: tuple[tuple[str, str | None], ...],
    label: str,
) -> None:
    events = report.get("events")
    if not isinstance(events, list):
        raise RealtimeScenarioError(f"RT004 {label} snapshot has no event list")
    lifecycle = [
        event
        for event in events
        if isinstance(event, dict) and event.get("type") in CYCLE_TYPES
    ]
    actual = [
        (event["type"], event.get("session_id"))
        for event in lifecycle
    ]
    if actual != list(expected):
        raise RealtimeScenarioError(
            f"RT004 {label} lifecycle was missing, duplicated, stale, or misordered"
        )


class AutomaticCloseRecoveryRunner(RealtimeRunnerBase):
    def __init__(self, *, scenario: dict[str, object], **kwargs: object) -> None:
        validate_scenario(scenario)
        super().__init__(scenario_id="RT004", **kwargs)
        self.scenario = scenario

    def run(self) -> dict[str, object]:
        stage = "preconditions"
        session_ids: list[str] = []
        initial_count = 0
        snapshots: dict[str, dict[str, object]] = {}
        try:
            initial = self.report()
            if initial.get("state") != "wake_owned" or initial.get("wake_microphone_open") is not True:
                raise RealtimeScenarioError(
                    "RT004 requires an armed host in wake_owned with the wake microphone open"
                )
            if not self.wake_fixture.exists():
                raise RealtimeScenarioError(f"RT004 wake fixture is missing: {self.wake_fixture}")
            events = initial.get("events")
            initial_count = len(events) if isinstance(events, list) else 0

            for cycle, active_key, recovered_key in (
                ("a", "active_a", "between"),
                ("b", "active_b", "final"),
            ):
                stage = f"session_{cycle}_connect"
                self.play(self.wake_fixture)
                active = self.wait(
                    lambda report: report.get("state") == "host_active"
                    and report.get("wake_microphone_open") is False,
                    f"exclusive host_active for session {cycle.upper()}",
                )
                snapshots[active_key] = active
                connected = [
                    event for event in active.get("events", [])[initial_count:]
                    if isinstance(event, dict) and event.get("type") == "host_connected"
                ]
                if len(connected) != len(session_ids) + 1:
                    raise RealtimeScenarioError(
                        f"RT004 session {cycle.upper()} did not expose exactly one fresh connection"
                    )
                session_id = connected[-1].get("session_id")
                if not isinstance(session_id, str) or not session_id:
                    raise RealtimeScenarioError(
                        f"RT004 session {cycle.upper()} did not expose a session identity"
                    )
                if session_id in session_ids:
                    raise RealtimeScenarioError("RT004 next wake reused the first session identity")
                session_ids.append(session_id)

                stage = f"session_{cycle}_cleanup"
                self.stop()
                recovered = self.wait(
                    lambda report: report.get("state") == "wake_owned"
                    and report.get("wake_microphone_open") is True,
                    f"wake ownership after session {cycle.upper()} stop",
                )
                snapshots[recovered_key] = recovered

            observation = build_observation(
                session_ids=(session_ids[0], session_ids[1]),
                active_a=snapshots["active_a"],
                between=snapshots["between"],
                active_b=snapshots["active_b"],
                final=snapshots["final"],
                initial_event_count=initial_count,
            )
            return self._evidence(observation, evaluate_observation(self.scenario, observation))
        except Exception as exc:
            try:
                self.stop()
            except Exception:
                pass
            try:
                current = self.report()
            except Exception:
                current = {}
            observation: dict[str, object] = {
                "session_ids": session_ids,
                "current": sanitize_report(current),
            }
            evidence = self._evidence(
                observation,
                {
                    "result": "failed",
                    "failure_stage": stage,
                    "failure_reason": self._safe_failure(exc),
                },
            )
            raise RealtimeRunFailure(self._safe_failure(exc), evidence) from exc

    def _evidence(
        self,
        observation: dict[str, object],
        result: dict[str, object],
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "scenario_id": "RT004",
            "scenario_version": self.scenario["version"],
            "evidence_tier": "live_host",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "observation": observation,
            "privacy": "allowlisted sanitized lifecycle metadata only",
        }

    @staticmethod
    def _safe_failure(exc: Exception) -> str:
        if isinstance(exc, RealtimeScenarioError):
            return str(exc)[:240]
        return f"RT004 live dependency failed: {type(exc).__name__}"


def write_evidence(path: Path, evidence: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.realtime_close_recovery")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO_PATH)
    commands = parser.add_subparsers(dest="command", required=True)
    offline = commands.add_parser("offline")
    offline.add_argument("observation", type=Path)
    live = commands.add_parser("live")
    live.add_argument("--base-url", default="http://127.0.0.1:8770")
    live.add_argument("--timeout", type=float, default=30.0)
    live.add_argument("--wake-fixture", type=Path)
    live.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    args = parser.parse_args(argv)
    try:
        scenario = load_scenario(args.scenario)
        if args.command == "offline":
            observation = json.loads(args.observation.read_text(encoding="utf-8"))
            print(json.dumps(evaluate_observation(scenario, observation), sort_keys=True))
            return 0
        runner = AutomaticCloseRecoveryRunner(
            scenario=scenario,
            base_url=args.base_url,
            wake_fixture=args.wake_fixture,
            transition_timeout=args.timeout,
        )
        evidence = runner.run()
        write_evidence(args.evidence_output, evidence)
        print(json.dumps(evidence["result"], sort_keys=True))
        return 0
    except RealtimeRunFailure as exc:
        write_evidence(args.evidence_output, exc.evidence)
        print(f"RT004 evaluation failed: {exc}")
        return 1
    except (RealtimeScenarioError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"RT004 evaluation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

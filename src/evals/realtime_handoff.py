"""Automatic RT001 wake-to-exclusive-Realtime-handoff evaluation."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.evals.realtime_common import (
    PROJECT_ROOT,
    RealtimeRunFailure,
    RealtimeRunnerBase,
    RealtimeScenarioError,
    sanitize_report,
    validate_scenario_contract,
)


DEFAULT_SCENARIO_PATH = PROJECT_ROOT / "evals" / "realtime" / "scenarios" / "RT001.json"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "tmp" / "realtime-evals" / "RT001-evidence.json"
ORDERED_EVENTS = (
    "wake_microphone_closed",
    "host_microphone_requested",
    "host_microphone_acquired",
    "host_connected",
    "host_stopped",
    "wake_microphone_reopened",
)


def load_scenario(path: Path = DEFAULT_SCENARIO_PATH) -> dict[str, object]:
    try:
        scenario = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealtimeScenarioError(f"RT001 scenario could not be loaded: {exc}") from exc
    if not isinstance(scenario, dict):
        raise RealtimeScenarioError("RT001 scenario must be an object")
    validate_scenario(scenario)
    return scenario


def validate_scenario(scenario: dict[str, object]) -> None:
    validate_scenario_contract(scenario, expected_id="RT001")
    oracles = scenario["oracles"]
    expected = {
        "connected_state": "host_active",
        "wake_microphone_open_during_host": False,
        "final_state": "wake_owned",
        "wake_microphone_open": True,
    }
    if any(oracles.get(key) != value for key, value in expected.items()):
        raise RealtimeScenarioError("RT001 ownership and recovery oracles must remain fail-closed")


def build_observation(
    *,
    active_report: dict[str, object],
    final_report: dict[str, object],
    session_id: str,
    initial_event_count: int = 0,
) -> dict[str, object]:
    active_raw = dict(active_report)
    final_raw = dict(final_report)
    active_events = active_report.get("events")
    final_events = final_report.get("events")
    active_raw["events"] = (
        active_events[initial_event_count:] if isinstance(active_events, list) else []
    )
    final_raw["events"] = (
        final_events[initial_event_count:] if isinstance(final_events, list) else []
    )
    active = sanitize_report(active_raw)
    final = sanitize_report(final_raw)
    return {"session_id": session_id, "active_report": active, "final_report": final}


def evaluate_observation(
    scenario: dict[str, object],
    observation: dict[str, object],
) -> dict[str, object]:
    validate_scenario(scenario)
    session_id = observation.get("session_id")
    active = observation.get("active_report")
    final = observation.get("final_report")
    if not isinstance(session_id, str) or not session_id:
        raise RealtimeScenarioError("RT001 observation is missing a session identity")
    if not isinstance(active, dict) or not isinstance(final, dict):
        raise RealtimeScenarioError("RT001 observation requires active and final sanitized reports")
    oracles = scenario["oracles"]
    if (
        active.get("state") != oracles["connected_state"]
        or active.get("wake_microphone_open") is not oracles["wake_microphone_open_during_host"]
    ):
        raise RealtimeScenarioError(
            "RT001 connected snapshot did not hold exclusive browser microphone ownership"
        )
    if (
        final.get("state") != oracles["final_state"]
        or final.get("wake_microphone_open") is not oracles["wake_microphone_open"]
    ):
        raise RealtimeScenarioError("RT001 cleanup did not restore wake_owned with the wake microphone open")

    events = final.get("events")
    if not isinstance(events, list):
        raise RealtimeScenarioError("RT001 sanitized report has no event list")
    _require_ordered_lifecycle(events, ORDERED_EVENTS, session_id, snapshot="final")
    session_lifecycle = {
        event.get("session_id")
        for event in events
        if isinstance(event, dict) and event.get("type") in ORDERED_EVENTS[1:]
    }
    if session_lifecycle != {session_id}:
        raise RealtimeScenarioError("RT001 observed stale or wrong-session lifecycle events")
    active_events = active.get("events")
    if not isinstance(active_events, list):
        raise RealtimeScenarioError("RT001 active snapshot has no event list")
    _require_ordered_lifecycle(
        active_events,
        ORDERED_EVENTS[:4],
        session_id,
        snapshot="active",
    )
    active_sessions = {
        event.get("session_id")
        for event in active_events
        if isinstance(event, dict) and event.get("type") in ORDERED_EVENTS[1:4]
    }
    if active_sessions != {session_id}:
        raise RealtimeScenarioError(
            "RT001 active snapshot observed stale or wrong-session lifecycle events"
        )
    return {
        "result": "passed",
        "session_id": session_id,
        "exclusive_handoff": True,
        "connected": True,
        "recovered_to_wake": True,
    }


def _require_ordered_lifecycle(
    events: list[object],
    expected_types: tuple[str, ...],
    session_id: str,
    *,
    snapshot: str,
) -> None:
    positions: list[int] = []
    for event_type in expected_types:
        matches = [
            index
            for index, event in enumerate(events)
            if isinstance(event, dict)
            and event.get("type") == event_type
            and (
                event_type == "wake_microphone_closed"
                or event.get("session_id") == session_id
            )
        ]
        if not matches:
            raise RealtimeScenarioError(
                f"RT001 {snapshot} snapshot is missing {event_type} for the active session"
            )
        if len(matches) != 1:
            raise RealtimeScenarioError(
                f"RT001 {snapshot} snapshot duplicated {event_type} for the active session"
            )
        positions.append(matches[0])
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise RealtimeScenarioError(
            f"RT001 {snapshot} snapshot lifecycle events were misordered"
        )


class AutomaticHandoffRunner(RealtimeRunnerBase):
    def __init__(self, *, scenario: dict[str, object], **kwargs: object) -> None:
        validate_scenario(scenario)
        super().__init__(scenario_id="RT001", **kwargs)
        self.scenario = scenario

    def run(self) -> dict[str, object]:
        stage = "preconditions"
        session_id: str | None = None
        initial_count = 0
        active: dict[str, object] | None = None
        try:
            initial = self.report()
            if initial.get("state") != "wake_owned" or initial.get("wake_microphone_open") is not True:
                raise RealtimeScenarioError(
                    "RT001 requires an armed host in wake_owned with the wake microphone open"
                )
            if not self.wake_fixture.exists():
                raise RealtimeScenarioError(f"RT001 wake fixture is missing: {self.wake_fixture}")
            events = initial.get("events")
            initial_count = len(events) if isinstance(events, list) else 0

            stage = "wake_and_connect"
            self.play(self.wake_fixture)
            active = self.wait(
                lambda report: report.get("state") == "host_active"
                and report.get("wake_microphone_open") is False,
                "exclusive host_active after saved wake",
            )
            new_events = active.get("events")
            new_events = new_events[initial_count:] if isinstance(new_events, list) else []
            connected = next(
                (
                    event
                    for event in reversed(new_events)
                    if isinstance(event, dict) and event.get("type") == "host_connected"
                ),
                None,
            )
            session_id = connected.get("session_id") if isinstance(connected, dict) else None
            if not isinstance(session_id, str) or not session_id:
                raise RealtimeScenarioError("RT001 active host did not expose a fresh session identity")

            stage = "cleanup"
            self.stop()
            final = self.wait(
                lambda report: report.get("state") == "wake_owned"
                and report.get("wake_microphone_open") is True,
                "wake ownership after explicit stop",
            )
            observation = build_observation(
                active_report=active,
                final_report=final,
                session_id=session_id,
                initial_event_count=initial_count,
            )
            result = evaluate_observation(self.scenario, observation)
            return self._evidence(observation, result)
        except Exception as exc:
            try:
                self.stop()
            except Exception:
                pass
            try:
                final = self.report()
            except Exception:
                final = {"state": "unknown", "wake_microphone_open": False, "events": []}
            observation: dict[str, object] = {
                "active_report": sanitize_report(active or {}),
                "final_report": sanitize_report(final),
            }
            if session_id:
                observation["session_id"] = session_id
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
            "scenario_id": "RT001",
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
        return f"RT001 live dependency failed: {type(exc).__name__}"


def write_evidence(path: Path, evidence: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.realtime_handoff")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO_PATH)
    commands = parser.add_subparsers(dest="command", required=True)
    offline = commands.add_parser("offline", help="evaluate a saved sanitized RT001 observation")
    offline.add_argument("observation", type=Path)
    live = commands.add_parser("live", help="automatically run RT001 against an armed local host")
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
        runner = AutomaticHandoffRunner(
            scenario=scenario,
            base_url=args.base_url,
            wake_fixture=args.wake_fixture,
            transition_timeout=args.timeout,
        )
        evidence = runner.run()
        write_evidence(args.evidence_output, evidence)
        print(json.dumps(evidence["result"], sort_keys=True))
        print(f"Saved sanitized RT001 evidence to {args.evidence_output}")
        return 0
    except RealtimeRunFailure as exc:
        write_evidence(args.evidence_output, exc.evidence)
        print(f"RT001 evaluation failed: {exc}")
        print(f"Saved sanitized RT001 failure evidence to {args.evidence_output}")
        return 1
    except (RealtimeScenarioError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"RT001 evaluation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

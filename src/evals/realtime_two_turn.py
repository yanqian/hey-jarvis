"""Automatic RT002 two-turn private-fixture Realtime evaluation."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import urllib.request
import wave
from array import array
from datetime import datetime, timezone
from pathlib import Path

from src.evals.realtime_common import (
    DEFAULT_FIXTURE_ROOT,
    PROJECT_ROOT,
    RealtimeRunFailure,
    RealtimeRunnerBase,
    RealtimeScenarioError,
    sanitize_report,
    validate_scenario_contract,
)
from src.realtime.fixtures import load_manifest


DEFAULT_SCENARIO_PATH = PROJECT_ROOT / "evals/realtime/scenarios/RT002.json"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "tmp/realtime-evals/RT002-evidence.json"
TURN_EVENT_TYPES = (
    "host_fixture_submitted",
    "host_response_created",
    "host_response_done",
)


def load_scenario(path: Path = DEFAULT_SCENARIO_PATH) -> dict[str, object]:
    try:
        scenario = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealtimeScenarioError(f"RT002 scenario could not be loaded: {exc}") from exc
    if not isinstance(scenario, dict):
        raise RealtimeScenarioError("RT002 scenario must be an object")
    validate_scenario(scenario)
    return scenario


def validate_scenario(scenario: dict[str, object]) -> None:
    validate_scenario_contract(scenario, expected_id="RT002")
    expected = {
        "connection_count": 1,
        "turn_count": 2,
        "response_reason": "completed",
        "final_state": "wake_owned",
        "wake_microphone_open": True,
    }
    if scenario["oracles"] != expected:
        raise RealtimeScenarioError("RT002 two-turn continuity oracles must remain fail-closed")


def build_observation(
    report: dict[str, object],
    *,
    session_id: str,
    initial_event_count: int = 0,
) -> dict[str, object]:
    raw = dict(report)
    events = report.get("events")
    raw["events"] = events[initial_event_count:] if isinstance(events, list) else []
    return {"session_id": session_id, "report": sanitize_report(raw)}


def evaluate_observation(
    scenario: dict[str, object],
    observation: dict[str, object],
) -> dict[str, object]:
    validate_scenario(scenario)
    session_id = observation.get("session_id")
    report = observation.get("report")
    if not isinstance(session_id, str) or not session_id:
        raise RealtimeScenarioError("RT002 observation is missing a session identity")
    if not isinstance(report, dict) or not isinstance(report.get("events"), list):
        raise RealtimeScenarioError("RT002 observation is missing a sanitized event report")
    if (
        report.get("state") != "wake_owned"
        or report.get("wake_microphone_open") is not True
    ):
        raise RealtimeScenarioError("RT002 cleanup did not restore wake ownership")
    events = report["events"]
    scoped_types = {"host_connected", *TURN_EVENT_TYPES, "host_stopped", "wake_microphone_reopened"}
    wrong = [
        event for event in events
        if isinstance(event, dict)
        and event.get("type") in scoped_types
        and event.get("session_id") != session_id
    ]
    if wrong:
        raise RealtimeScenarioError("RT002 observed stale or wrong-session lifecycle events")
    connected = _events(events, "host_connected")
    if len(connected) != 1:
        raise RealtimeScenarioError(f"RT002 observed {len(connected)} connections, expected exactly one")
    per_type = {kind: _events(events, kind) for kind in TURN_EVENT_TYPES}
    for kind, found in per_type.items():
        if len(found) != 2:
            raise RealtimeScenarioError(f"RT002 observed {len(found)} {kind} events, expected exactly two")
    stops = _events(events, "host_stopped")
    reopened = _events(events, "wake_microphone_reopened")
    if len(stops) != 1 or len(reopened) != 1:
        raise RealtimeScenarioError("RT002 cleanup lifecycle must occur exactly once")
    ordered = [connected[0]]
    for turn in range(2):
        ordered.extend(per_type[kind][turn] for kind in TURN_EVENT_TYPES)
        done = per_type["host_response_done"][turn]
        if done.get("reason") != "completed":
            raise RealtimeScenarioError(
                f"RT002 turn {turn + 1} response ended as {done.get('reason')!r}, expected 'completed'"
            )
    ordered.extend((stops[0], reopened[0]))
    positions = [events.index(event) for event in ordered]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise RealtimeScenarioError("RT002 speech, response, and cleanup lifecycle was misordered")
    return {
        "result": "passed",
        "session_id": session_id,
        "connection_count": 1,
        "turn_count": 2,
        "responses_completed": 2,
        "recovered_to_wake": True,
    }


def _events(events: list[object], event_type: str) -> list[dict[str, object]]:
    return [
        event for event in events
        if isinstance(event, dict) and event.get("type") == event_type
    ]


def verified_fixture(root: Path, name: str) -> Path:
    manifest = load_manifest(root)
    metadata = manifest.get(name)
    if metadata is None:
        raise RealtimeScenarioError(f"RT002 fixture metadata is missing for {name}")
    path = root / f"{name}.wav"
    expected = metadata.sha256
    replay = root / "replay" / f"{name}.wav"
    replay_manifest = root / "replay-manifest.json"
    if replay.exists():
        try:
            payload = json.loads(replay_manifest.read_text(encoding="utf-8"))
            expected = payload["replay"][name]["sha256"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RealtimeScenarioError(f"RT002 replay fixture metadata is invalid for {name}") from exc
        path = replay
    if not path.exists():
        raise RealtimeScenarioError(f"RT002 fixture file is missing for {name}")
    try:
        with wave.open(str(path), "rb") as source:
            pcm = source.readframes(source.getnframes())
    except wave.Error as exc:
        raise RealtimeScenarioError(f"RT002 fixture WAV is invalid for {name}") from exc
    if hashlib.sha256(pcm).hexdigest() != expected:
        raise RealtimeScenarioError(f"RT002 fixture integrity mismatch for {name}")
    return path


class AutomaticTwoTurnRunner(RealtimeRunnerBase):
    def __init__(
        self,
        *,
        scenario: dict[str, object],
        fixture_root: Path = DEFAULT_FIXTURE_ROOT,
        inject: object | None = None,
        **kwargs: object,
    ):
        validate_scenario(scenario)
        super().__init__(scenario_id="RT002", **kwargs)
        self.scenario = scenario
        self.fixture_root = fixture_root
        self.inject = inject or self._inject_fixture

    def run(self) -> dict[str, object]:
        stage = "preconditions"
        session_id: str | None = None
        initial_count = 0
        try:
            initial = self.report()
            if initial.get("state") != "wake_owned" or initial.get("wake_microphone_open") is not True:
                raise RealtimeScenarioError("RT002 requires an armed host with wake ownership")
            fixtures = {name: verified_fixture(self.fixture_root, name) for name in ("wake", "turn-1", "turn-2")}
            initial_count = len(initial.get("events", []))
            stage = "connect"
            self.play(fixtures["wake"])
            active = self.wait(lambda report: report.get("state") == "host_active", "one active session")
            new = active.get("events", [])[initial_count:]
            connected = [event for event in new if isinstance(event, dict) and event.get("type") == "host_connected"]
            if len(connected) != 1 or not isinstance(connected[0].get("session_id"), str):
                raise RealtimeScenarioError("RT002 did not expose exactly one fresh connection")
            session_id = str(connected[0]["session_id"])
            for turn, fixture_name in enumerate(("turn-1", "turn-2"), start=1):
                stage = f"turn_{turn}"
                self.inject(fixtures[fixture_name])
                active = self.wait(
                    lambda report, target=turn: len([
                        event for event in report.get("events", [])[initial_count:]
                        if isinstance(event, dict)
                        and event.get("type") == "host_response_done"
                        and event.get("session_id") == session_id
                    ]) >= target,
                    f"completed response for turn {turn}",
                )
                completed = [
                    event for event in active.get("events", [])[initial_count:]
                    if isinstance(event, dict)
                    and event.get("type") == "host_response_done"
                    and event.get("session_id") == session_id
                ]
                if completed[-1].get("reason") != "completed":
                    raise RealtimeScenarioError(
                        f"RT002 turn {turn} response ended as {completed[-1].get('reason')!r}, "
                        "expected 'completed'"
                    )
            stage = "cleanup"
            self.stop()
            final = self.wait(
                lambda report: report.get("state") == "wake_owned"
                and report.get("wake_microphone_open") is True,
                "wake ownership after two turns",
            )
            observation = build_observation(final, session_id=session_id, initial_event_count=initial_count)
            return self._evidence(observation, evaluate_observation(self.scenario, observation))
        except Exception as exc:
            try:
                self.stop()
            except Exception:
                pass
            try:
                final = self.report()
            except Exception:
                final = {}
            observation: dict[str, object] = {"report": sanitize_report(final)}
            if session_id:
                observation["session_id"] = session_id
            evidence = self._evidence(observation, {
                "result": "failed", "failure_stage": stage, "failure_reason": self._safe_failure(exc)
            })
            raise RealtimeRunFailure(self._safe_failure(exc), evidence) from exc

    def _evidence(self, observation: dict[str, object], result: dict[str, object]) -> dict[str, object]:
        return {
            "schema_version": 1, "scenario_id": "RT002",
            "scenario_version": self.scenario["version"], "evidence_tier": "fixture_replay",
            "created_at": datetime.now(timezone.utc).isoformat(), "result": result,
            "observation": observation, "privacy": "allowlisted sanitized lifecycle metadata only",
        }

    def _inject_fixture(self, path: Path) -> None:
        audio = fixture_pcm24_base64(path)
        body = json.dumps({"name": path.stem, "audio": audio}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/fixture-audio",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5.0) as response:
            payload = json.loads(response.read())
        if payload.get("status") != "requested":
            raise RealtimeScenarioError(f"RT002 fixture injection was rejected for {path.stem}")

    @staticmethod
    def _safe_failure(exc: Exception) -> str:
        return str(exc)[:240] if isinstance(exc, RealtimeScenarioError) else f"RT002 live dependency failed: {type(exc).__name__}"


def fixture_pcm24_base64(path: Path) -> str:
    """Return one atomic 24 kHz mono PCM16 conversation item."""

    try:
        with wave.open(str(path), "rb") as source:
            if (
                source.getnchannels(),
                source.getsampwidth(),
                source.getframerate(),
            ) != (1, 2, 16_000):
                raise RealtimeScenarioError("RT002 fixture format must be mono 16 kHz PCM16")
            source_samples = array("h", source.readframes(source.getnframes()))
    except wave.Error as exc:
        raise RealtimeScenarioError(f"RT002 fixture WAV is invalid for {path.stem}") from exc
    if not source_samples:
        raise RealtimeScenarioError(f"RT002 fixture audio is empty for {path.stem}")
    output = array("h")
    output_count = round(len(source_samples) * 24_000 / 16_000)
    for output_index in range(output_count):
        position = output_index * 16_000 / 24_000
        left = min(int(position), len(source_samples) - 1)
        right = min(left + 1, len(source_samples) - 1)
        fraction = position - left
        output.append(round(source_samples[left] * (1.0 - fraction) + source_samples[right] * fraction))
    return base64.b64encode(output.tobytes()).decode("ascii")


def write_evidence(path: Path, evidence: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.realtime_two_turn")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO_PATH)
    commands = parser.add_subparsers(dest="command", required=True)
    offline = commands.add_parser("offline")
    offline.add_argument("observation", type=Path)
    live = commands.add_parser("live")
    live.add_argument("--base-url", default="http://127.0.0.1:8770")
    live.add_argument("--timeout", type=float, default=30.0)
    live.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    live.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE_PATH)
    args = parser.parse_args(argv)
    try:
        scenario = load_scenario(args.scenario)
        if args.command == "offline":
            print(json.dumps(evaluate_observation(scenario, json.loads(args.observation.read_text())), sort_keys=True))
            return 0
        runner = AutomaticTwoTurnRunner(
            scenario=scenario, fixture_root=args.fixture_root, base_url=args.base_url,
            wake_fixture=None, transition_timeout=args.timeout,
        )
        evidence = runner.run()
        write_evidence(args.evidence_output, evidence)
        print(json.dumps(evidence["result"], sort_keys=True))
        return 0
    except RealtimeRunFailure as exc:
        write_evidence(args.evidence_output, exc.evidence)
        print(f"RT002 evaluation failed: {exc}")
        return 1
    except (RealtimeScenarioError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"RT002 evaluation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

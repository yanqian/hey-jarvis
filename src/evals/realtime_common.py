"""Shared, privacy-bounded machinery for spec-driven Realtime evaluations."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "evals" / "realtime" / "scenario.schema.json"
DEFAULT_FIXTURE_ROOT = PROJECT_ROOT / "tmp" / "realtime-fixtures"
HANDOFF_PHASE_TIMING_FIELDS = frozenset(
    {
        "command_to_token_ms",
        "token_ms",
        "microphone_ms",
        "peer_setup_ms",
        "negotiation_ms",
        "session_configuration_ms",
    }
)
PEER_SETUP_TIMING_FIELDS = frozenset(
    {
        "microphone_reporting_ms",
        "audio_analysis_setup_ms",
        "peer_connection_setup_ms",
        "offer_creation_ms",
        "local_description_ms",
    }
)
HANDOFF_TIMING_FIELDS = frozenset(
    {
        *HANDOFF_PHASE_TIMING_FIELDS,
        *PEER_SETUP_TIMING_FIELDS,
        "total_browser_ready_ms",
    }
)
SAFE_EVENT_FIELDS = frozenset({"type", "at_ms", "session_id", "reason", *HANDOFF_TIMING_FIELDS})
SAFE_EVENT_TYPES = frozenset(
    {
        "wake_confirmed",
        "wake_microphone_closed",
        "ack_started",
        "ack_completed",
        "handoff_queued",
        "host_microphone_requested",
        "host_microphone_acquired",
        "host_handoff_timing",
        "host_connected",
        "host_fixture_submitted",
        "host_response_created",
        "host_speech_started",
        "host_speech_stopped",
        "host_response_done",
        "host_stopped",
        "wake_microphone_reopened",
    }
)
SAFE_EVENT_REASONS = frozenset(
    {"cancelled", "completed", "explicit", "end_phrase", "idle_timeout", "max_duration", "error", "test"}
)
SAFE_REPORT_STATES = frozenset(
    {"wake_owned", "python_stopping", "host_starting", "host_active", "host_stopping"}
)


class RealtimeScenarioError(RuntimeError):
    """Raised when a generic scenario contract or observation is invalid."""


class RealtimeRunFailure(RealtimeScenarioError):
    """A live failure carrying bounded sanitized evidence."""

    def __init__(self, message: str, evidence: dict[str, object]) -> None:
        super().__init__(message)
        self.evidence = evidence


def load_schema(path: Path = DEFAULT_SCHEMA_PATH) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealtimeScenarioError(f"Realtime scenario schema could not be loaded: {exc}") from exc
    if not isinstance(value, dict):
        raise RealtimeScenarioError("Realtime scenario schema must be an object")
    return value


def validate_scenario_contract(
    scenario: dict[str, object],
    *,
    expected_id: str,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    schema = load_schema(schema_path)
    missing = [field for field in schema["required"] if field not in scenario]
    if missing:
        raise RealtimeScenarioError(
            f"{expected_id} scenario is missing required fields: {', '.join(missing)}"
        )
    if scenario.get("id") != expected_id or scenario.get("schema_version") != 1:
        raise RealtimeScenarioError(
            f"{expected_id} scenario must use id {expected_id} and schema_version 1"
        )
    if not isinstance(scenario.get("version"), int) or int(scenario["version"]) < 1:
        raise RealtimeScenarioError(f"{expected_id} scenario version must be a positive integer")

    contracts = schema.get("scenario_contracts")
    contract = contracts.get(expected_id) if isinstance(contracts, dict) else None
    if not isinstance(contract, dict):
        raise RealtimeScenarioError(f"Realtime schema has no contract for {expected_id}")
    oracles = scenario.get("oracles")
    if not isinstance(oracles, dict):
        raise RealtimeScenarioError(f"{expected_id} oracles must be an object")
    missing_oracles = [field for field in contract["oracle_required"] if field not in oracles]
    if missing_oracles:
        raise RealtimeScenarioError(
            f"{expected_id} scenario is missing oracles: {', '.join(missing_oracles)}"
        )
    actions = scenario.get("human_actions")
    if not isinstance(actions, list) or len(actions) != contract["human_action_count"]:
        raise RealtimeScenarioError(
            f"{expected_id} must require exactly {contract['human_action_count']} human actions"
        )
    evidence = scenario.get("evidence")
    tiers = evidence.get("required") if isinstance(evidence, dict) else None
    if tiers != contract["evidence_tiers"]:
        raise RealtimeScenarioError(
            f"{expected_id} must require {' and '.join(contract['evidence_tiers'])} evidence"
        )
    allowed_tiers = schema.get("allowed_evidence_tiers")
    if not isinstance(allowed_tiers, list) or any(tier not in allowed_tiers for tier in tiers):
        raise RealtimeScenarioError(f"{expected_id} uses an unsupported evidence tier")
    privacy = scenario.get("privacy")
    if not isinstance(privacy, dict):
        raise RealtimeScenarioError(f"{expected_id} privacy rules must be an object")
    if privacy.get("commit_audio") is not False or privacy.get("commit_transcript") is not False:
        raise RealtimeScenarioError(f"{expected_id} must prohibit committed audio and transcripts")
    fields = privacy.get("allowed_event_fields")
    if not isinstance(fields, list) or set(fields) - SAFE_EVENT_FIELDS:
        raise RealtimeScenarioError(f"{expected_id} allowed event fields exceed the evaluator allowlist")
    forbidden = privacy.get("forbidden_fields")
    if not isinstance(forbidden, list) or not {
        "audio",
        "transcript",
        "api_key",
        "token",
    }.issubset(forbidden):
        raise RealtimeScenarioError(
            f"{expected_id} privacy rules do not forbid required sensitive fields"
        )


def sanitize_report(report: dict[str, object]) -> dict[str, object]:
    safe_events: list[dict[str, object]] = []
    events = report.get("events")
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        if event.get("type") not in SAFE_EVENT_TYPES or not isinstance(event.get("at_ms"), int):
            continue
        safe: dict[str, object] = {"type": event["type"], "at_ms": int(event["at_ms"])}
        if isinstance(event.get("session_id"), str):
            safe["session_id"] = str(event["session_id"])[:128]
        reason = event.get("reason")
        if isinstance(reason, str) and reason in SAFE_EVENT_REASONS:
            safe["reason"] = reason
        elif "reason" in event:
            safe["reason"] = "redacted"
        if event.get("type") == "host_handoff_timing":
            for field in HANDOFF_TIMING_FIELDS:
                value = event.get(field)
                if isinstance(value, int) and not isinstance(value, bool):
                    safe[field] = value
        safe_events.append(safe)
    state = report.get("state")
    return {
        "state": state if state in SAFE_REPORT_STATES else "unknown",
        "wake_microphone_open": report.get("wake_microphone_open") is True,
        "events": safe_events[-200:],
    }


def json_request(url: str, *, method: str = "GET") -> dict[str, object]:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=3.0) as response:
        return json.loads(response.read())


class RealtimeRunnerBase:
    """Injected I/O, polling, playback, and bounded cleanup shared by live evals."""

    def __init__(
        self,
        *,
        scenario_id: str,
        base_url: str,
        wake_fixture: Path | None,
        request: Callable[..., dict[str, object]] = json_request,
        play: Callable[[Path], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        transition_timeout: float = 30.0,
    ) -> None:
        self.scenario_id = scenario_id
        self.base_url = base_url.rstrip("/")
        self.wake_fixture = wake_fixture or self.default_wake_fixture()
        self.request = request
        self.play = play or self.afplay
        self.clock = clock
        self.sleep = sleep
        self.transition_timeout = transition_timeout

    def report(self) -> dict[str, object]:
        return self.request(f"{self.base_url}/api/report")

    def stop(self) -> dict[str, object]:
        return self.request(f"{self.base_url}/api/stop", method="POST")

    def wait(
        self,
        predicate: Callable[[dict[str, object]], bool],
        label: str,
    ) -> dict[str, object]:
        deadline = self.clock() + self.transition_timeout
        while self.clock() < deadline:
            report = self.report()
            if predicate(report):
                return report
            self.sleep(0.1)
        raise RealtimeScenarioError(f"{self.scenario_id} timed out waiting for {label}")

    @staticmethod
    def afplay(path: Path) -> None:
        subprocess.run(["afplay", str(path)], check=True)

    @staticmethod
    def default_wake_fixture() -> Path:
        replay = DEFAULT_FIXTURE_ROOT / "replay" / "wake.wav"
        return replay if replay.exists() else DEFAULT_FIXTURE_ROOT / "wake.wav"

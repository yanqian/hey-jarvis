from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.evals.realtime_common import RealtimeRunFailure, RealtimeScenarioError, sanitize_report
from src.evals.realtime_handoff import (
    DEFAULT_SCENARIO_PATH,
    AutomaticHandoffRunner,
    build_observation,
    evaluate_observation,
    load_scenario,
    main,
    validate_scenario,
)


SESSION = "session-rt001"
TIMING = {
    "command_to_token_ms": 1,
    "token_ms": 2,
    "microphone_ms": 3,
    "peer_setup_ms": 2,
    "microphone_reporting_ms": 1,
    "audio_analysis_setup_ms": 0,
    "input_level_cleanup_ms": 0,
    "audio_context_creation_ms": 0,
    "analyser_setup_ms": 0,
    "media_stream_source_creation_ms": 0,
    "source_connection_ms": 0,
    "monitor_startup_ms": 0,
    "peer_connection_setup_ms": 0,
    "offer_creation_ms": 1,
    "local_description_ms": 0,
    "negotiation_ms": 5,
    "session_configuration_ms": 2,
    "total_browser_ready_ms": 15,
}


def event(at_ms: int, event_type: str, session_id: str | None = SESSION, **detail: object):
    value: dict[str, object] = {"at_ms": at_ms, "type": event_type, **detail}
    if session_id is not None:
        value["session_id"] = session_id
    return value


def reports() -> tuple[dict[str, object], dict[str, object]]:
    active_events = [
        event(10, "wake_confirmed", None),
        event(11, "wake_microphone_closed", None, reason="handoff"),
        event(12, "ack_started", None),
        event(22, "ack_completed", None),
        event(23, "handoff_queued"),
        event(24, "host_microphone_requested"),
        event(25, "host_microphone_acquired"),
        event(39, "host_handoff_timing", **TIMING),
        event(40, "host_connected"),
    ]
    active = {
        "state": "host_active",
        "wake_microphone_open": False,
        "events": active_events,
    }
    final = {
        "state": "wake_owned",
        "wake_microphone_open": True,
        "events": [
            *active_events,
            event(50, "host_stopped", reason="explicit"),
            event(60, "wake_microphone_reopened"),
        ],
    }
    return active, final


def passing_observation() -> dict[str, object]:
    active, final = reports()
    return build_observation(
        active_report=active,
        final_report=final,
        session_id=SESSION,
    )


class RT001ContractTests(unittest.TestCase):
    def test_scenario_matches_authoritative_no_human_matrix(self):
        scenario = load_scenario()
        self.assertEqual(scenario["id"], "RT001")
        self.assertEqual(scenario["version"], 5)
        self.assertEqual(scenario["human_actions"], [])
        self.assertEqual(scenario["evidence"]["required"], ["offline", "live_host"])
        self.assertNotIn("response", json.dumps(scenario["oracles"]))
        self.assertIs(scenario["oracles"]["input_level_analysis_enabled"], False)

    def test_generic_schema_validation_fails_closed(self):
        scenario = load_scenario()
        cases = (
            ("missing", "goal", "missing required fields"),
            ("human", "human_actions", "exactly 0"),
            ("tier", "evidence", "offline and live_host"),
            ("privacy", "privacy", "prohibit committed"),
            ("oracle", "oracles", "fail-closed"),
        )
        for name, field, expected in cases:
            with self.subTest(name=name):
                candidate = deepcopy(scenario)
                if name == "missing":
                    candidate.pop(field)
                elif name == "human":
                    candidate[field] = [{"source": "live"}]
                elif name == "tier":
                    candidate[field]["required"] = ["offline"]
                elif name == "privacy":
                    candidate[field]["commit_audio"] = True
                else:
                    candidate[field]["wake_microphone_open"] = False
                with self.assertRaisesRegex(RealtimeScenarioError, expected):
                    validate_scenario(candidate)

    def test_shared_sanitizer_is_bounded_and_drops_sensitive_content(self):
        active, _ = reports()
        active["events"][0].update(
            {"transcript": "private", "audio": "base64", "api_key": "secret"}
        )
        active["events"] = [
            *active["events"],
            *[event(100 + index, "host_connected") for index in range(205)],
        ]
        sanitized = sanitize_report(active)
        self.assertEqual(len(sanitized["events"]), 200)
        encoded = json.dumps(sanitized)
        for value in ("private", "base64", "secret", "transcript", "api_key"):
            self.assertNotIn(value, encoded)


class RT001OracleTests(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenario()

    def assert_failure(self, observation: dict[str, object], expected: str):
        with self.assertRaisesRegex(RealtimeScenarioError, expected):
            evaluate_observation(self.scenario, observation)

    def test_valid_exclusive_handoff_passes(self):
        result = evaluate_observation(self.scenario, passing_observation())
        self.assertTrue(result["exclusive_handoff"])
        self.assertTrue(result["connected"])
        self.assertTrue(result["recovered_to_wake"])
        self.assertEqual(result["timing_ms"]["acknowledgement_ms"], 10)
        self.assertEqual(result["timing_ms"]["handoff_dispatch_ms"], 2)
        self.assertEqual(result["timing_ms"]["wake_to_ready_ms"], 30)

    def test_timing_fields_fail_closed_without_weakening_lifecycle(self):
        for name, mutate, expected in (
            (
                "missing",
                lambda timing: timing.pop("token_ms"),
                "missing browser fields",
            ),
            (
                "negative",
                lambda timing: timing.__setitem__("token_ms", -1),
                "token_ms was invalid",
            ),
            (
                "mismatch",
                lambda timing: timing.__setitem__("total_browser_ready_ms", 1),
                "did not match",
            ),
            (
                "peer-missing",
                lambda timing: timing.pop("offer_creation_ms"),
                "missing browser fields",
            ),
            (
                "peer-negative",
                lambda timing: timing.__setitem__("offer_creation_ms", -1),
                "offer_creation_ms was invalid",
            ),
            (
                "peer-mismatch",
                lambda timing: timing.__setitem__("offer_creation_ms", 20),
                "peer setup subphases did not match",
            ),
            (
                "audio-analysis-missing",
                lambda timing: timing.pop("audio_context_creation_ms"),
                "missing browser fields",
            ),
            (
                "audio-analysis-negative",
                lambda timing: timing.__setitem__("audio_context_creation_ms", -1),
                "audio_context_creation_ms was invalid",
            ),
            (
                "audio-analysis-mismatch",
                lambda timing: timing.__setitem__("audio_context_creation_ms", 20),
                "audio analysis subphases did not match",
            ),
        ):
            with self.subTest(name=name):
                observation = passing_observation()
                timing = next(
                    item
                    for item in observation["final_report"]["events"]
                    if item["type"] == "host_handoff_timing"
                )
                mutate(timing)
                self.assert_failure(observation, expected)

    def test_normal_path_rejects_a_valid_but_enabled_audio_analyser(self):
        observation = passing_observation()
        timing = next(
            item
            for item in observation["final_report"]["events"]
            if item["type"] == "host_handoff_timing"
        )
        timing.update(
            {
                "audio_analysis_setup_ms": 1,
                "audio_context_creation_ms": 1,
                "peer_setup_ms": 3,
                "total_browser_ready_ms": 16,
            }
        )
        self.assert_failure(observation, "unexpectedly enabled input-level")

    def test_missing_duplicated_and_misordered_events_fail_precisely(self):
        for name, mutate, expected in (
            (
                "missing",
                lambda events: events.__setitem__(
                    slice(None), [item for item in events if item["type"] != "host_microphone_acquired"]
                ),
                "missing host_microphone_acquired",
            ),
            (
                "duplicate",
                lambda events: events.insert(7, deepcopy(events[6])),
                "duplicated host_microphone_acquired",
            ),
            (
                "misordered",
                lambda events: events.__setitem__(
                    slice(None), [events[0], events[2], events[1], *events[3:]]
                ),
                "misordered",
            ),
        ):
            with self.subTest(name=name):
                observation = passing_observation()
                mutate(observation["final_report"]["events"])
                self.assert_failure(observation, expected)

    def test_stale_wrong_session_and_cleanup_defect_fail(self):
        stale = passing_observation()
        stale["final_report"]["events"][8]["session_id"] = "session-stale"
        self.assert_failure(stale, "missing host_connected")

        extra = passing_observation()
        extra["final_report"]["events"].append(event(45, "host_connected", "session-stale"))
        self.assert_failure(extra, "stale or wrong-session")

        cleanup = passing_observation()
        cleanup["final_report"]["state"] = "host_stopping"
        cleanup["final_report"]["wake_microphone_open"] = False
        self.assert_failure(cleanup, "cleanup did not restore")

    def test_active_snapshot_must_prove_exclusive_current_handoff(self):
        observation = passing_observation()
        observation["active_report"]["wake_microphone_open"] = True
        self.assert_failure(observation, "exclusive browser")
        observation = passing_observation()
        observation["active_report"]["events"] = observation["active_report"]["events"][:-1]
        self.assert_failure(observation, "active snapshot is missing host_connected")

    def test_active_snapshot_rejects_wrong_session_and_duplicate_connection(self):
        wrong = passing_observation()
        wrong["active_report"]["events"][8]["session_id"] = "session-stale"
        self.assert_failure(wrong, "active snapshot is missing host_connected")

        duplicated = passing_observation()
        duplicated["active_report"]["events"].append(
            deepcopy(duplicated["active_report"]["events"][8])
        )
        self.assert_failure(duplicated, "active snapshot duplicated host_connected")


class FakeRT001Host:
    def __init__(self, *, connect: bool = True, cleanup: bool = True, fail_first_stop: bool = False):
        self.state = "wake_owned"
        self.mic_open = True
        self.events = [event(1, "host_response_created", "old-session")]
        self.now = 10
        self.connect = connect
        self.cleanup = cleanup
        self.fail_first_stop = fail_first_stop
        self.stop_calls = 0
        self.play_calls = 0

    def add(self, event_type: str, session_id: str | None = SESSION, **detail: object):
        self.now += 10
        self.events.append(event(self.now, event_type, session_id, **detail))

    def play(self, _path: Path):
        self.play_calls += 1
        self.state = "host_starting"
        self.mic_open = False
        self.add("wake_confirmed", None)
        self.add("wake_microphone_closed", None, reason="handoff")
        self.add("ack_started", None)
        self.add("ack_completed", None)
        self.add("handoff_queued")
        self.add("host_microphone_requested")
        self.add("host_microphone_acquired")
        if self.connect:
            self.add("host_handoff_timing", **{
                **TIMING,
                "total_browser_ready_ms": 5,
                "command_to_token_ms": 0,
                "token_ms": 1,
                "microphone_ms": 1,
                "peer_setup_ms": 1,
                "microphone_reporting_ms": 0,
                "audio_analysis_setup_ms": 0,
                "input_level_cleanup_ms": 0,
                "audio_context_creation_ms": 0,
                "analyser_setup_ms": 0,
                "media_stream_source_creation_ms": 0,
                "source_connection_ms": 0,
                "monitor_startup_ms": 0,
                "peer_connection_setup_ms": 0,
                "offer_creation_ms": 1,
                "local_description_ms": 0,
                "negotiation_ms": 1,
                "session_configuration_ms": 1,
            })
            self.add("host_connected")
            self.state = "host_active"

    def request(self, url: str, *, method: str = "GET"):
        if url.endswith("/api/report"):
            return {
                "state": self.state,
                "wake_microphone_open": self.mic_open,
                "events": deepcopy(self.events),
            }
        if url.endswith("/api/stop"):
            self.stop_calls += 1
            if self.fail_first_stop and self.stop_calls == 1:
                raise OSError("private provider body must not leak")
            if self.cleanup:
                self.add("host_stopped", reason="explicit")
                self.add("wake_microphone_reopened")
                self.state = "wake_owned"
                self.mic_open = True
            return {"ok": True}
        raise AssertionError((url, method))


class RT001RunnerTests(unittest.TestCase):
    def build_runner(self, directory: str, host: FakeRT001Host, **kwargs):
        wake = Path(directory) / "wake.wav"
        wake.write_bytes(b"private-fixture")
        now = [0.0]
        runner = AutomaticHandoffRunner(
            scenario=load_scenario(),
            base_url="http://local",
            wake_fixture=wake,
            request=host.request,
            play=host.play,
            clock=lambda: now[0],
            sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
            transition_timeout=0.3,
            **kwargs,
        )
        return runner

    def test_live_runner_is_automatic_and_emits_sanitized_pass(self):
        host = FakeRT001Host()
        with tempfile.TemporaryDirectory() as directory:
            evidence = self.build_runner(directory, host).run()
        self.assertEqual(host.play_calls, 1)
        self.assertEqual(host.stop_calls, 1)
        self.assertEqual(evidence["evidence_tier"], "live_host")
        self.assertEqual(evidence["result"]["result"], "passed")
        encoded = json.dumps(evidence)
        for forbidden in ('"transcript":', '"audio":', '"api_key":', "private-fixture"):
            self.assertNotIn(forbidden, encoded)

    def test_connection_timeout_requests_cleanup_and_records_stage(self):
        host = FakeRT001Host(connect=False)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RealtimeRunFailure, "timed out") as caught:
                self.build_runner(directory, host).run()
        self.assertEqual(host.stop_calls, 1)
        self.assertEqual(caught.exception.evidence["result"]["failure_stage"], "wake_and_connect")

    def test_stop_failure_and_cleanup_defect_fail_with_bounded_evidence(self):
        for name, host, expected in (
            ("stop", FakeRT001Host(fail_first_stop=True), "OSError"),
            ("cleanup", FakeRT001Host(cleanup=False), "timed out"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(RealtimeRunFailure, expected) as caught:
                    self.build_runner(directory, host).run()
                self.assertEqual(caught.exception.evidence["result"]["failure_stage"], "cleanup")
                self.assertNotIn("private provider body", json.dumps(caught.exception.evidence))

    def test_offline_cli_uses_same_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observation.json"
            path.write_text(json.dumps(passing_observation()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--scenario", str(DEFAULT_SCENARIO_PATH), "offline", str(path)])
        self.assertEqual(code, 0)
        self.assertIn('"result": "passed"', output.getvalue())


if __name__ == "__main__":
    unittest.main()

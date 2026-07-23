from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
import wave
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from src.evals.realtime_common import RealtimeRunFailure, RealtimeScenarioError
from src.evals.realtime_two_turn import (
    AutomaticTwoTurnRunner,
    build_observation,
    evaluate_observation,
    load_scenario,
    main,
    fixture_pcm24_base64,
    verified_fixture,
)


SESSION = "session-rt002"


def event(at_ms: int, kind: str, session: str = SESSION, **detail: object):
    return {"at_ms": at_ms, "type": kind, "session_id": session, **detail}


def passing_observation():
    events = [event(10, "host_connected")]
    at = 20
    for _turn in range(2):
        events.extend(
            [
                event(at, "host_fixture_submitted"),
                event(at + 10, "host_response_created"),
                event(at + 20, "host_response_done", reason="completed"),
            ]
        )
        at += 40
    events.extend(
        [
            event(at, "host_stopped", reason="explicit"),
            event(at + 10, "wake_microphone_reopened"),
        ]
    )
    return build_observation(
        {"state": "wake_owned", "wake_microphone_open": True, "events": events},
        session_id=SESSION,
    )


class RT002ContractAndOracleTests(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenario()

    def assert_failure(self, observation, expected):
        with self.assertRaisesRegex(RealtimeScenarioError, expected):
            evaluate_observation(self.scenario, observation)

    def test_contract_has_zero_routine_human_actions_and_fixture_replay_tier(self):
        self.assertEqual(self.scenario["human_actions"], [])
        self.assertEqual(self.scenario["evidence"]["required"], ["offline", "fixture_replay"])
        self.assertEqual(self.scenario["oracles"]["turn_count"], 2)

    def test_exactly_two_ordered_turns_in_one_session_pass(self):
        result = evaluate_observation(self.scenario, passing_observation())
        self.assertEqual(result["connection_count"], 1)
        self.assertEqual(result["turn_count"], 2)
        self.assertEqual(result["responses_completed"], 2)

    def test_second_connection_and_wrong_session_fail(self):
        duplicate = passing_observation()
        duplicate["report"]["events"].insert(1, event(11, "host_connected"))
        self.assert_failure(duplicate, "2 connections")
        wrong = passing_observation()
        wrong["report"]["events"][5]["session_id"] = "session-stale"
        self.assert_failure(wrong, "wrong-session")

    def test_missing_extra_and_early_second_fixture_submission_fail(self):
        missing = passing_observation()
        missing["report"]["events"] = [
            item for item in missing["report"]["events"]
            if not (item["type"] == "host_fixture_submitted" and item["at_ms"] > 50)
        ]
        self.assert_failure(missing, "1 host_fixture_submitted")
        extra = passing_observation()
        extra["report"]["events"].insert(-2, event(115, "host_fixture_submitted"))
        self.assert_failure(extra, "3 host_fixture_submitted")
        early = passing_observation()
        second = [
            item for item in early["report"]["events"]
            if item["type"] == "host_fixture_submitted"
        ][1]
        early["report"]["events"].remove(second)
        early["report"]["events"].insert(2, second)
        self.assert_failure(early, "misordered")

    def test_cancelled_response_intervening_close_and_cleanup_fail(self):
        cancelled = passing_observation()
        [item for item in cancelled["report"]["events"] if item["type"] == "host_response_done"][1][
            "reason"
        ] = "cancelled"
        self.assert_failure(cancelled, "turn 2 response ended")
        closed = passing_observation()
        closed["report"]["events"].insert(5, closed["report"]["events"].pop(-2))
        self.assert_failure(closed, "misordered")
        cleanup = passing_observation()
        cleanup["report"]["state"] = "host_stopping"
        cleanup["report"]["wake_microphone_open"] = False
        self.assert_failure(cleanup, "cleanup did not restore")


class RT002FixtureIntegrityTests(unittest.TestCase):
    def write_fixture(self, root: Path, name: str = "turn-1") -> Path:
        pcm = b"\x01\x00" * 1600
        path = root / f"{name}.wav"
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(pcm)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"fixtures": {}}
        manifest["fixtures"][name] = {
            "name": name,
            "filename": path.name,
            "duration_seconds": 0.1,
            "sample_rate": 16000,
            "channels": 1,
            "sample_width_bytes": 2,
            "sha256": hashlib.sha256(pcm).hexdigest(),
            "overflow_chunks": 0,
            "recorded_at": "2026-01-01T00:00:00Z",
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def write_all_fixtures(self, root: Path) -> None:
        for name in ("wake", "turn-1", "turn-2"):
            self.write_fixture(root, name)

    def test_valid_fixture_and_integrity_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_fixture(root)
            self.assertEqual(verified_fixture(root, "turn-1"), path)
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\x02\x00" * 1600)
            with self.assertRaisesRegex(RealtimeScenarioError, "integrity mismatch"):
                verified_fixture(root, "turn-1")

    def test_missing_metadata_and_file_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RealtimeScenarioError, "metadata is missing"):
                verified_fixture(root, "turn-1")
            path = self.write_fixture(root)
            path.unlink()
            with self.assertRaisesRegex(RealtimeScenarioError, "file is missing"):
                verified_fixture(root, "turn-1")

    def test_automatic_runner_replays_three_fixtures_and_cleans_up(self):
        class Host:
            def __init__(self):
                self.state = "wake_owned"
                self.open = True
                self.events = []
                self.now = 0
                self.plays = []
                self.injects = []

            def add(self, kind, **detail):
                self.now += 10
                self.events.append(event(self.now, kind, **detail))

            def play(self, path):
                self.plays.append(path.stem)
                if path.stem == "wake":
                    self.open = False
                    self.state = "host_active"
                    self.add("host_connected")

            def inject(self, path):
                self.injects.append(path.stem)
                self.add("host_fixture_submitted")
                self.add("host_response_created")
                self.add("host_response_done", reason="completed")

            def request(self, url, *, method="GET"):
                if url.endswith("/api/report"):
                    return {
                        "state": self.state,
                        "wake_microphone_open": self.open,
                        "events": deepcopy(self.events),
                    }
                if url.endswith("/api/stop"):
                    self.add("host_stopped", reason="explicit")
                    self.add("wake_microphone_reopened")
                    self.state = "wake_owned"
                    self.open = True
                    return {"ok": True}
                raise AssertionError((url, method))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_all_fixtures(root)
            host = Host()
            runner = AutomaticTwoTurnRunner(
                scenario=load_scenario(),
                fixture_root=root,
                base_url="http://local",
                wake_fixture=None,
                request=host.request,
                play=host.play,
                inject=host.inject,
                sleep=lambda _seconds: None,
            )
            evidence = runner.run()
        self.assertEqual(host.plays, ["wake"])
        self.assertEqual(host.injects, ["turn-1", "turn-2"])
        self.assertEqual(evidence["result"]["turn_count"], 2)
        self.assertEqual(evidence["evidence_tier"], "fixture_replay")

    def test_turn_timeout_fails_at_precise_stage_and_attempts_cleanup(self):
        class Host:
            def __init__(self):
                self.state = "wake_owned"
                self.open = True
                self.events = []
                self.stop_calls = 0

            def play(self, path):
                if path.stem == "wake":
                    self.state = "host_active"
                    self.open = False
                    self.events.append(event(10, "host_connected"))

            def request(self, url, *, method="GET"):
                if url.endswith("/api/report"):
                    return {
                        "state": self.state,
                        "wake_microphone_open": self.open,
                        "events": deepcopy(self.events),
                    }
                if url.endswith("/api/stop"):
                    self.stop_calls += 1
                    self.events.extend(
                        [
                            event(20, "host_stopped", reason="explicit"),
                            event(30, "wake_microphone_reopened"),
                        ]
                    )
                    self.state = "wake_owned"
                    self.open = True
                    return {"ok": True}
                raise AssertionError((url, method))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_all_fixtures(root)
            host = Host()
            ticks = iter(range(100))
            runner = AutomaticTwoTurnRunner(
                scenario=load_scenario(),
                fixture_root=root,
                base_url="http://local",
                wake_fixture=None,
                request=host.request,
                play=host.play,
                inject=lambda _path: None,
                clock=lambda: next(ticks),
                sleep=lambda _seconds: None,
                transition_timeout=2,
            )
            with self.assertRaises(RealtimeRunFailure) as raised:
                runner.run()
        self.assertEqual(raised.exception.evidence["result"]["failure_stage"], "turn_1")
        self.assertIn("timed out", raised.exception.evidence["result"]["failure_reason"])
        self.assertEqual(host.stop_calls, 1)

    def test_cleanup_timeout_is_not_relabelled_as_success(self):
        class Host:
            def __init__(self):
                self.state = "wake_owned"
                self.open = True
                self.events = []
                self.now = 0
                self.stop_calls = 0

            def add(self, kind, **detail):
                self.now += 10
                self.events.append(event(self.now, kind, **detail))

            def play(self, path):
                if path.stem == "wake":
                    self.state = "host_active"
                    self.open = False
                    self.add("host_connected")

            def inject(self, _path):
                self.add("host_fixture_submitted")
                self.add("host_response_created")
                self.add("host_response_done", reason="completed")

            def request(self, url, *, method="GET"):
                if url.endswith("/api/report"):
                    return {
                        "state": self.state,
                        "wake_microphone_open": self.open,
                        "events": deepcopy(self.events),
                    }
                if url.endswith("/api/stop"):
                    self.stop_calls += 1
                    return {"ok": True}
                raise AssertionError((url, method))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_all_fixtures(root)
            host = Host()
            ticks = iter(range(100))
            runner = AutomaticTwoTurnRunner(
                scenario=load_scenario(),
                fixture_root=root,
                base_url="http://local",
                wake_fixture=None,
                request=host.request,
                play=host.play,
                inject=host.inject,
                clock=lambda: next(ticks),
                sleep=lambda _seconds: None,
                transition_timeout=2,
            )
            with self.assertRaises(RealtimeRunFailure) as raised:
                runner.run()
        self.assertEqual(raised.exception.evidence["result"]["failure_stage"], "cleanup")
        self.assertIn("timed out", raised.exception.evidence["result"]["failure_reason"])
        self.assertEqual(host.stop_calls, 2)

    def test_fixture_payload_is_resampled_to_one_pcm24_item(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_fixture(Path(directory), "turn-1")
            decoded = base64.b64decode(fixture_pcm24_base64(path))
        self.assertEqual(len(decoded), round(0.1 * 24_000) * 2)

    def test_offline_cli_evaluates_a_sanitized_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            observation = Path(directory) / "observation.json"
            observation.write_text(json.dumps(passing_observation()), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                status = main(["offline", str(observation)])
        self.assertEqual(status, 0)
        self.assertIn('"turn_count": 2', output.getvalue())


if __name__ == "__main__":
    unittest.main()

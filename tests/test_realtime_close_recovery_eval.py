from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.evals.realtime_close_recovery import (
    AutomaticCloseRecoveryRunner,
    build_observation,
    evaluate_observation,
    load_scenario,
    main,
)
from src.evals.realtime_common import RealtimeRunFailure, RealtimeScenarioError


SESSION_A = "session-rt004-a"
SESSION_B = "session-rt004-b"


def event(at_ms: int, kind: str, session_id: str | None = None, **detail: object):
    value = {"at_ms": at_ms, "type": kind, **detail}
    if session_id is not None:
        value["session_id"] = session_id
    return value


def cycle(start: int, session_id: str):
    return [
        event(start, "wake_microphone_closed", reason="handoff"),
        event(start + 10, "host_microphone_requested", session_id),
        event(start + 20, "host_microphone_acquired", session_id),
        event(start + 30, "host_connected", session_id),
        event(start + 40, "host_stopped", session_id, reason="explicit"),
        event(start + 50, "wake_microphone_reopened", session_id),
    ]


def passing_observation():
    first = cycle(10, SESSION_A)
    second = cycle(80, SESSION_B)
    return build_observation(
        session_ids=(SESSION_A, SESSION_B),
        active_a={"state": "host_active", "wake_microphone_open": False, "events": first[:4]},
        between={"state": "wake_owned", "wake_microphone_open": True, "events": first},
        active_b={
            "state": "host_active",
            "wake_microphone_open": False,
            "events": [*first, *second[:4]],
        },
        final={
            "state": "wake_owned",
            "wake_microphone_open": True,
            "events": [*first, *second],
        },
    )


class RT004OracleTests(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenario()

    def assert_failure(self, observation, expected):
        with self.assertRaisesRegex(RealtimeScenarioError, expected):
            evaluate_observation(self.scenario, observation)

    def test_contract_and_valid_two_session_lifecycle(self):
        self.assertEqual(self.scenario["human_actions"], [])
        self.assertEqual(self.scenario["evidence"]["required"], ["offline", "live_host"])
        result = evaluate_observation(self.scenario, passing_observation())
        self.assertEqual(result["session_count"], 2)
        self.assertTrue(result["distinct_session_ids"])
        self.assertEqual(result["media_cleanup_cycles"], 2)

    def test_reused_or_stale_session_identity_fails(self):
        reused = passing_observation()
        reused["session_ids"][1] = SESSION_A
        self.assert_failure(reused, "reused")
        stale = passing_observation()
        stale["final"]["events"][9]["session_id"] = "session-stale"
        self.assert_failure(stale, "stale")

    def test_missing_misordered_or_duplicated_cleanup_fails(self):
        missing = passing_observation()
        missing["final"]["events"] = [
            item for item in missing["final"]["events"]
            if not (item["type"] == "host_stopped" and item.get("session_id") == SESSION_B)
        ]
        self.assert_failure(missing, "missing")
        misordered = passing_observation()
        events = misordered["final"]["events"]
        events[-2], events[-1] = events[-1], events[-2]
        self.assert_failure(misordered, "misordered")
        duplicate = passing_observation()
        duplicate["final"]["events"].insert(-1, deepcopy(duplicate["final"]["events"][-2]))
        self.assert_failure(duplicate, "duplicated")

    def test_concurrent_ownership_and_cleanup_snapshot_fail(self):
        active = passing_observation()
        active["active_b"]["wake_microphone_open"] = True
        self.assert_failure(active, "exclusive browser")
        between = passing_observation()
        between["between"]["state"] = "host_stopping"
        between["between"]["wake_microphone_open"] = False
        self.assert_failure(between, "first cleanup")

    def test_offline_cli_uses_same_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observation.json"
            path.write_text(json.dumps(passing_observation()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(["offline", str(path)])
        self.assertEqual(status, 0)
        self.assertIn('"session_count": 2', output.getvalue())


class FakeRT004Host:
    def __init__(
        self,
        *,
        connect_second: bool = True,
        cleanup_a: bool = True,
        cleanup_b: bool = True,
        reuse_identity: bool = False,
    ):
        self.state = "wake_owned"
        self.open = True
        self.events = [event(1, "host_response_created", "old-session")]
        self.now = 10
        self.play_calls = 0
        self.stop_calls = 0
        self.connect_second = connect_second
        self.cleanup_a = cleanup_a
        self.cleanup_b = cleanup_b
        self.reuse_identity = reuse_identity

    def add(self, kind, session_id=None, **detail):
        self.now += 10
        self.events.append(event(self.now, kind, session_id, **detail))

    def current_session(self):
        if self.play_calls == 1 or self.reuse_identity:
            return SESSION_A
        return SESSION_B

    def play(self, _path):
        self.play_calls += 1
        self.state = "host_starting"
        self.open = False
        session_id = self.current_session()
        self.add("wake_microphone_closed", reason="handoff")
        self.add("host_microphone_requested", session_id)
        self.add("host_microphone_acquired", session_id)
        if self.play_calls == 1 or self.connect_second:
            self.add("host_connected", session_id)
            self.state = "host_active"

    def request(self, url, *, method="GET"):
        if url.endswith("/api/report"):
            return {
                "state": self.state,
                "wake_microphone_open": self.open,
                "events": deepcopy(self.events),
            }
        if url.endswith("/api/stop"):
            self.stop_calls += 1
            cleanup = self.cleanup_a if self.stop_calls == 1 else self.cleanup_b
            if cleanup:
                session_id = self.current_session()
                self.add("host_stopped", session_id, reason="explicit")
                self.add("wake_microphone_reopened", session_id)
                self.state = "wake_owned"
                self.open = True
            return {"ok": True}
        raise AssertionError((url, method))


class RT004RunnerTests(unittest.TestCase):
    def runner(self, directory, host):
        wake = Path(directory) / "wake.wav"
        wake.write_bytes(b"private-wake")
        now = [0.0]
        return AutomaticCloseRecoveryRunner(
            scenario=load_scenario(),
            base_url="http://local",
            wake_fixture=wake,
            request=host.request,
            play=host.play,
            clock=lambda: now[0],
            sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
            transition_timeout=0.3,
        )

    def test_runner_automatically_connects_and_cleans_two_sessions(self):
        host = FakeRT004Host()
        with tempfile.TemporaryDirectory() as directory:
            evidence = self.runner(directory, host).run()
        self.assertEqual(host.play_calls, 2)
        self.assertEqual(host.stop_calls, 2)
        self.assertEqual(evidence["result"]["session_count"], 2)
        encoded = json.dumps(evidence)
        for forbidden in ("private-wake", "transcript", "audio", "api_key"):
            self.assertNotIn(forbidden, encoded)

    def test_second_connection_failure_and_reused_identity_fail_precisely(self):
        for host, expected, stage in (
            (FakeRT004Host(connect_second=False), "timed out", "session_b_connect"),
            (FakeRT004Host(reuse_identity=True), "reused", "session_b_connect"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(RealtimeRunFailure, expected) as caught:
                    self.runner(directory, host).run()
            self.assertEqual(caught.exception.evidence["result"]["failure_stage"], stage)

    def test_either_cleanup_timeout_is_a_precise_failure(self):
        for host, stage in (
            (FakeRT004Host(cleanup_a=False), "session_a_cleanup"),
            (FakeRT004Host(cleanup_b=False), "session_b_cleanup"),
        ):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(RealtimeRunFailure, "timed out") as caught:
                    self.runner(directory, host).run()
            self.assertEqual(caught.exception.evidence["result"]["failure_stage"], stage)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.evals.realtime_barge_in import (
    DEFAULT_SCENARIO_PATH,
    AssistedBargeInRunner,
    RealtimeEvalError,
    RealtimeLiveFailure,
    build_observation,
    evaluate_observation,
    load_scenario,
    main,
    sanitize_report,
    validate_scenario,
)


SESSION_ID = "session-rt003"


def event(at_ms: int, event_type: str, **detail: object) -> dict[str, object]:
    return {"at_ms": at_ms, "type": event_type, "session_id": SESSION_ID, **detail}


def passing_report() -> dict[str, object]:
    return {
        "state": "wake_owned",
        "wake_microphone_open": True,
        "events": [
            event(50, "host_connected"),
            event(100, "host_response_created"),
            event(200, "host_speech_started"),
            event(240, "host_response_done", reason="cancelled"),
            event(250, "host_speech_stopped"),
            event(300, "host_response_created"),
            event(500, "host_response_done", reason="completed"),
            event(600, "host_stopped", reason="explicit"),
        ],
    }


def passing_observation() -> dict[str, object]:
    return build_observation(
        report=passing_report(),
        session_id=SESSION_ID,
        long_response_created_at_ms=100,
    )


class ScenarioContractTests(unittest.TestCase):
    def test_checked_in_scenario_is_versioned_private_and_requires_two_evidence_tiers(self):
        scenario = load_scenario()
        self.assertEqual(scenario["id"], "RT003")
        self.assertEqual(scenario["version"], 2)
        self.assertEqual(scenario["oracles"]["cancellation_latency_ms_max"], 1000)
        self.assertEqual(scenario["evidence"]["required"], ["offline", "live_near_end"])
        self.assertFalse(scenario["privacy"]["commit_audio"])
        self.assertFalse(scenario["privacy"]["commit_transcript"])
        self.assertEqual(len(scenario["human_actions"]), 1)

    def test_schema_validation_rejects_missing_or_unsafe_contract_fields(self):
        scenario = load_scenario()
        cases = (
            ("goal", None, "missing required fields"),
            ("latency", 0, "positive integer"),
            ("two_actions", None, "exactly one"),
            ("audio", True, "prohibit committed"),
            ("unsafe_field", None, "exceed"),
        )
        for name, value, expected in cases:
            with self.subTest(name=name):
                candidate = deepcopy(scenario)
                if name == "goal":
                    candidate.pop("goal")
                elif name == "latency":
                    candidate["oracles"]["cancellation_latency_ms_max"] = value
                elif name == "two_actions":
                    candidate["human_actions"].append(deepcopy(candidate["human_actions"][0]))
                elif name == "audio":
                    candidate["privacy"]["commit_audio"] = value
                else:
                    candidate["privacy"]["allowed_event_fields"].append("transcript")
                with self.assertRaisesRegex(RealtimeEvalError, expected):
                    validate_scenario(candidate)

    def test_report_sanitizer_uses_a_bounded_allowlist(self):
        report = passing_report()
        sensitive_event = report["events"][0]
        sensitive_event.update(
            {
                "transcript": "private words",
                "audio": "base64",
                "arguments": {"secret": True},
                "api_key": "secret",
                "reason": {"transcript": "nested private words"},
            }
        )
        report["events"] = [
            {"type": "ignored-without-time", "transcript": "private"},
            *report["events"][1:],
            *[
                event(1000 + index, "host_response_created", transcript="private")
                for index in range(205)
            ],
            sensitive_event,
        ]
        sanitized = sanitize_report(report)
        self.assertEqual(len(sanitized["events"]), 200)
        encoded = json.dumps(sanitized)
        for forbidden in ("private words", "base64", "arguments", "api_key", "transcript"):
            self.assertNotIn(forbidden, encoded)
        self.assertIn('"reason": "redacted"', encoded)
        self.assertLessEqual(
            set(sanitized["events"][0]),
            {"type", "at_ms", "session_id", "reason"},
        )


class RealtimeOracleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = load_scenario()

    def test_passing_observation_reports_latency_continuation_and_recovery(self):
        result = evaluate_observation(self.scenario, passing_observation())
        self.assertEqual(result["result"], "passed")
        self.assertEqual(result["cancellation_latency_ms"], 40)
        self.assertEqual(result["old_response_reason"], "cancelled")
        self.assertEqual(result["continuation_reason"], "completed")
        self.assertTrue(result["recovered_to_wake"])

    def assert_failure(self, observation: dict[str, object], expected: str) -> None:
        with self.assertRaisesRegex(RealtimeEvalError, expected):
            evaluate_observation(self.scenario, observation)

    def test_missing_or_wrong_session_speech_fails_precisely(self):
        missing = passing_observation()
        missing["report"]["events"] = [
            item for item in missing["report"]["events"] if item["type"] != "host_speech_started"
        ]
        self.assert_failure(missing, "did not observe near-end")

        wrong = passing_observation()
        next(item for item in wrong["report"]["events"] if item["type"] == "host_speech_started")[
            "session_id"
        ] = "session-stale"
        self.assert_failure(wrong, "active session")

    def test_non_cancelled_and_invalid_latency_fail(self):
        completed = passing_observation()
        next(item for item in completed["report"]["events"] if item["type"] == "host_response_done")[
            "reason"
        ] = "completed"
        self.assert_failure(completed, "expected 'cancelled'")

        negative = passing_observation()
        next(item for item in negative["report"]["events"] if item["type"] == "host_speech_started")[
            "at_ms"
        ] = 260
        self.assert_failure(negative, "negative")

        slow = passing_observation()
        done = next(item for item in slow["report"]["events"] if item["type"] == "host_response_done")
        done["at_ms"] = 1201
        self.assert_failure(slow, "exceeded 1000ms")

    def test_missing_or_failed_continuation_fails(self):
        missing = passing_observation()
        missing["report"]["events"] = [
            item for item in missing["report"]["events"] if int(item["at_ms"]) < 300
        ]
        self.assert_failure(missing, "continuation response.created")

        failed = passing_observation()
        failed["report"]["events"][-2]["reason"] = "failed"
        self.assert_failure(failed, "continuation ended as 'failed'")

    def test_stale_marker_and_cleanup_failure_fail(self):
        stale = passing_observation()
        stale["long_response_created_at_ms"] = 101
        self.assert_failure(stale, "marker is missing or stale")

        bad_state = passing_observation()
        bad_state["report"]["state"] = "host_stopping"
        bad_state["report"]["wake_microphone_open"] = False
        self.assert_failure(bad_state, "cleanup did not restore")


class FakeLiveHost:
    def __init__(self, *, complete_barge_in: bool = True) -> None:
        self.state = "wake_owned"
        self.mic_open = True
        self.events: list[dict[str, object]] = []
        self.now = 0
        self.complete_barge_in = complete_barge_in
        self.stop_calls = 0
        self.long_answer_requests = 0
        self.play_calls = 0

    def add(self, event_type: str, **detail: object) -> None:
        self.now += 100
        self.events.append(event(self.now, event_type, **detail))

    def play(self, _path: Path) -> None:
        self.play_calls += 1
        self.state = "host_active"
        self.mic_open = False
        self.add("host_connected")

    def request(self, url: str, *, method: str = "GET") -> dict[str, object]:
        if url.endswith("/api/report"):
            return {
                "state": self.state,
                "wake_microphone_open": self.mic_open,
                "events": deepcopy(self.events),
            }
        if url.endswith("/api/long-answer"):
            self.long_answer_requests += 1
            self.add("host_response_created")
            return {"ok": True}
        if url.endswith("/api/stop"):
            self.stop_calls += 1
            self.state = "wake_owned"
            self.mic_open = True
            self.add("host_stopped", reason="explicit")
            return {"ok": True}
        raise AssertionError((url, method))

    def emit_barge_in(self) -> None:
        self.add("host_speech_started")
        self.add("host_response_done", reason="cancelled")
        self.add("host_response_created")
        self.add("host_response_done", reason="completed")


class AssistedRunnerTests(unittest.TestCase):
    def test_guided_live_run_reuses_host_controls_and_emits_sanitized_evidence(self):
        host = FakeLiveHost()
        announcements: list[str] = []
        prompts: list[str] = []

        def operator_wait(prompt: str) -> None:
            prompts.append(prompt)
            self.assertEqual(host.play_calls, 0)
            self.assertEqual(host.long_answer_requests, 0)

        def announce(message: str) -> None:
            announcements.append(message)
            if "speak one natural interruption" in message:
                host.emit_barge_in()

        with tempfile.TemporaryDirectory() as directory:
            wake = Path(directory) / "wake.wav"
            wake.write_bytes(b"fixture-present")
            runner = AssistedBargeInRunner(
                scenario=load_scenario(),
                wake_fixture=wake,
                request=host.request,
                play=host.play,
                sleep=lambda _seconds: None,
                announce=announce,
                operator_wait=operator_wait,
            )
            evidence = runner.run()
        self.assertEqual(evidence["scenario_id"], "RT003")
        self.assertEqual(evidence["scenario_version"], 2)
        self.assertEqual(evidence["evidence_tier"], "live_near_end")
        self.assertEqual(evidence["result"]["cancellation_latency_ms"], 100)
        self.assertTrue(evidence["result"]["recovered_to_wake"])
        self.assertEqual(host.stop_calls, 1)
        self.assertEqual(len(prompts), 1)
        self.assertIn("press Enter to wake", prompts[0])
        self.assertIn("speak one natural interruption", announcements[0])
        encoded = json.dumps(evidence)
        for forbidden in ("transcript", "audio_delta", "api_key", "client_secret"):
            self.assertNotIn(forbidden, encoded)

    def test_timeout_requests_bounded_cleanup(self):
        host = FakeLiveHost(complete_barge_in=False)
        now = [0.0]
        with tempfile.TemporaryDirectory() as directory:
            wake = Path(directory) / "wake.wav"
            wake.write_bytes(b"fixture-present")
            runner = AssistedBargeInRunner(
                scenario=load_scenario(),
                wake_fixture=wake,
                request=host.request,
                play=host.play,
                clock=lambda: now[0],
                sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
                transition_timeout=0.5,
                announce=lambda _message: None,
                operator_wait=lambda _prompt: None,
            )
            with self.assertRaisesRegex(RealtimeLiveFailure, "timed out") as caught:
                runner.run()
        self.assertEqual(host.stop_calls, 1)
        self.assertEqual(caught.exception.evidence["result"]["result"], "failed")
        self.assertEqual(caught.exception.evidence["result"]["failure_stage"], "near_end_speech")
        self.assertEqual(
            caught.exception.evidence["observation"]["report"]["state"],
            "wake_owned",
        )

    def test_session_close_fails_early_with_sanitized_evidence(self):
        host = FakeLiveHost(complete_barge_in=False)

        original_request = host.request

        def close_after_long_answer(url: str, *, method: str = "GET") -> dict[str, object]:
            result = original_request(url, method=method)
            if url.endswith("/api/long-answer"):
                host.state = "wake_owned"
                host.mic_open = True
                host.add("host_stopped", reason="idle_timeout")
            return result

        with tempfile.TemporaryDirectory() as directory:
            wake = Path(directory) / "wake.wav"
            wake.write_bytes(b"fixture-present")
            runner = AssistedBargeInRunner(
                scenario=load_scenario(),
                wake_fixture=wake,
                request=close_after_long_answer,
                play=host.play,
                sleep=lambda _seconds: None,
                announce=lambda _message: None,
                operator_wait=lambda _prompt: None,
            )
            with self.assertRaisesRegex(RealtimeLiveFailure, "closed before") as caught:
                runner.run()
        evidence_text = json.dumps(caught.exception.evidence)
        self.assertIn('"result": "failed"', evidence_text)
        for forbidden in ("transcript", "audio_delta", "api_key", "client_secret"):
            self.assertNotIn(forbidden, evidence_text)

    def test_operator_cancel_and_closed_input_fail_closed_with_cleanup(self):
        for name, failure in (
            ("cancel", RealtimeEvalError("RT003 operator cancelled the readiness gate")),
            ("eof", EOFError()),
        ):
            with self.subTest(name=name):
                host = FakeLiveHost()

                def operator_wait(_prompt: str, error: BaseException = failure) -> None:
                    if isinstance(error, EOFError):
                        raise RealtimeEvalError(
                            "RT003 operator readiness input closed before confirmation"
                        ) from error
                    raise error

                with tempfile.TemporaryDirectory() as directory:
                    wake = Path(directory) / "wake.wav"
                    wake.write_bytes(b"fixture-present")
                    runner = AssistedBargeInRunner(
                        scenario=load_scenario(),
                        wake_fixture=wake,
                        request=host.request,
                        play=host.play,
                        announce=lambda _message: None,
                        operator_wait=operator_wait,
                    )
                    with self.assertRaises(RealtimeLiveFailure) as caught:
                        runner.run()
                self.assertEqual(host.long_answer_requests, 0)
                self.assertEqual(host.play_calls, 0)
                self.assertEqual(host.stop_calls, 1)
                self.assertEqual(
                    caught.exception.evidence["result"]["failure_stage"],
                    "operator_ready",
                )

    def test_answer_that_ends_before_near_end_speech_fails_precisely(self):
        host = FakeLiveHost()

        def announce(message: str) -> None:
            if "when counting is audible" in message:
                host.add("host_response_done", reason="completed")

        with tempfile.TemporaryDirectory() as directory:
            wake = Path(directory) / "wake.wav"
            wake.write_bytes(b"fixture-present")
            runner = AssistedBargeInRunner(
                scenario=load_scenario(),
                wake_fixture=wake,
                request=host.request,
                play=host.play,
                announce=announce,
                operator_wait=lambda _prompt: None,
            )
            with self.assertRaisesRegex(
                RealtimeLiveFailure,
                "ended as 'completed' before a valid near-end interruption",
            ) as caught:
                runner.run()
        self.assertEqual(host.stop_calls, 1)
        self.assertEqual(
            caught.exception.evidence["result"]["failure_stage"],
            "near_end_speech",
        )

    def test_cli_offline_evaluates_saved_observation_without_live_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            observation = Path(directory) / "observation.json"
            observation.write_text(json.dumps(passing_observation()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(["--scenario", str(DEFAULT_SCENARIO_PATH), "offline", str(observation)])
        self.assertEqual(exit_code, 0)
        self.assertIn('"result": "passed"', output.getvalue())
        self.assertIn('"cancellation_latency_ms": 40', output.getvalue())


if __name__ == "__main__":
    unittest.main()

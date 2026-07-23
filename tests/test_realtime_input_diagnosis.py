from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.evals.realtime_input_diagnosis import (
    AssistedInputDiagnosisRunner,
    RealtimeDiagnosisLiveFailure,
    build_diagnostic_observation,
    classify_diagnostic_observation,
    main,
    sanitize_diagnostic_report,
)


SESSION_ID = "session-f060"


def summary(max_rms: float, *, count: int = 3) -> dict[str, object]:
    return {
        "window_count": count,
        "max_rms": max_rms,
        "max_peak": min(1.0, max_rms * 2),
        "mean_rms": max_rms / 2,
    }


def observation(
    *,
    baseline: float = 0.002,
    no_playback: float = 0.03,
    remote_playback: float = 0.02,
    no_playback_vad: bool = False,
    remote_playback_vad: bool = False,
    count: int = 3,
) -> dict[str, object]:
    return {
        "summaries": {
            "silence": summary(baseline, count=count),
            "no_remote_playback_speech": summary(no_playback, count=count),
            "remote_playback_speech": summary(remote_playback, count=count),
        },
        "vad": {
            "no_remote_playback_speech_started": no_playback_vad,
            "remote_playback_speech_started": remote_playback_vad,
        },
        "cleanup": {"state": "wake_owned", "wake_microphone_open": True},
    }


class DiagnosticSanitizerTests(unittest.TestCase):
    def test_sanitizer_retains_only_bounded_normalized_level_metadata(self):
        events = [
            {
                "type": "host_input_level",
                "at_ms": index,
                "session_id": SESSION_ID,
                "phase": "remote_playback",
                "rms": 0.01234,
                "peak": 0.12345,
                "sampleCount": 5,
                "transcript": "private",
                "audio": "base64",
                "api_key": "secret",
            }
            for index in range(100)
        ]
        events.append(
            {
                "type": "host_response_done",
                "at_ms": 200,
                "session_id": SESSION_ID,
                "reason": "sk-secret transcript",
            }
        )
        events.append(
            {
                "type": "host_error",
                "at_ms": 201,
                "session_id": SESSION_ID,
                "reason": "webrtc_negotiation_failed",
                "httpStatus": 429,
                "errorType": "insufficient_quota",
                "errorCode": "insufficient_quota",
                "requestId": "req_safe_123",
                "retryAfter": "60",
                "rateLimitRemainingRequests": "0",
                "rateLimitResetRequests": "1m0s",
                "responseBody": "private provider body",
            }
        )
        sanitized = sanitize_diagnostic_report(
            {
                "state": "wake_owned",
                "wake_microphone_open": True,
                "events": events,
            }
        )
        levels = [
            event
            for event in sanitized["events"]
            if event["type"] == "host_input_level"
        ]
        self.assertEqual(len(levels), 80)
        self.assertEqual(levels[0]["rms"], 0.0123)
        self.assertEqual(levels[0]["peak"], 0.1235)
        encoded = json.dumps(sanitized)
        for forbidden in ("private", "base64", "api_key", "sk-secret", "transcript"):
            self.assertNotIn(forbidden, encoded)
        self.assertIn('"reason": "redacted"', encoded)
        self.assertIn('"httpStatus": 429', encoded)
        self.assertIn('"errorCode": "insufficient_quota"', encoded)
        self.assertIn('"requestId": "req_safe_123"', encoded)
        self.assertNotIn("private provider body", encoded)

    def test_build_observation_correlates_windows_vad_and_cleanup(self):
        report = {
            "state": "wake_owned",
            "wake_microphone_open": True,
            "events": [
                {
                    "type": "host_input_level",
                    "at_ms": 100,
                    "session_id": SESSION_ID,
                    "phase": "no_remote_playback",
                    "rms": 0.002,
                    "peak": 0.004,
                    "sampleCount": 5,
                },
                {
                    "type": "host_input_level",
                    "at_ms": 250,
                    "session_id": SESSION_ID,
                    "phase": "no_remote_playback",
                    "rms": 0.03,
                    "peak": 0.06,
                    "sampleCount": 5,
                },
                {
                    "type": "host_speech_started",
                    "at_ms": 260,
                    "session_id": SESSION_ID,
                },
                {
                    "type": "host_input_level",
                    "at_ms": 450,
                    "session_id": SESSION_ID,
                    "phase": "remote_playback",
                    "rms": 0.02,
                    "peak": 0.04,
                    "sampleCount": 5,
                },
            ],
        }
        result = build_diagnostic_observation(
            report=report,
            session_id=SESSION_ID,
            baseline_end_ms=100,
            no_playback_start_ms=200,
            remote_playback_start_ms=400,
        )
        self.assertEqual(result["summaries"]["silence"]["max_rms"], 0.002)
        self.assertEqual(
            result["summaries"]["no_remote_playback_speech"]["max_rms"], 0.03
        )
        self.assertEqual(result["summaries"]["remote_playback_speech"]["max_rms"], 0.02)
        self.assertTrue(result["vad"]["no_remote_playback_speech_started"])
        self.assertFalse(result["vad"]["remote_playback_speech_started"])

    def test_build_observation_summarizes_windows_beyond_saved_evidence_bound(self):
        report = {
            "state": "wake_owned",
            "wake_microphone_open": True,
            "events": [
                {
                    "type": "host_input_level",
                    "at_ms": index,
                    "session_id": SESSION_ID,
                    "phase": "no_remote_playback",
                    "rms": 0.002 if index < 5 else 0.3,
                    "peak": 0.004 if index < 5 else 0.6,
                    "sampleCount": 5,
                }
                for index in range(100)
            ]
            + [
                {
                    "type": "host_speech_started",
                    "at_ms": 95,
                    "session_id": SESSION_ID,
                },
                {
                    "type": "host_input_level",
                    "at_ms": 110,
                    "session_id": SESSION_ID,
                    "phase": "remote_playback",
                    "rms": 0.2,
                    "peak": 0.4,
                    "sampleCount": 5,
                },
                {
                    "type": "host_speech_started",
                    "at_ms": 111,
                    "session_id": SESSION_ID,
                },
            ],
        }
        result = build_diagnostic_observation(
            report=report,
            session_id=SESSION_ID,
            baseline_end_ms=4,
            no_playback_start_ms=5,
            remote_playback_start_ms=105,
        )
        self.assertEqual(result["summaries"]["silence"]["window_count"], 5)
        self.assertEqual(
            result["summaries"]["no_remote_playback_speech"]["max_rms"], 0.3
        )
        self.assertEqual(
            result["summaries"]["remote_playback_speech"]["max_rms"], 0.2
        )
        self.assertTrue(result["vad"]["no_remote_playback_speech_started"])
        self.assertTrue(result["vad"]["remote_playback_speech_started"])
        saved_levels = [
            event
            for event in result["report"]["events"]
            if event["type"] == "host_input_level"
        ]
        self.assertEqual(len(saved_levels), 80)


class DiagnosticClassifierTests(unittest.TestCase):
    def test_classifier_covers_all_diagnostic_categories(self):
        cases = (
            (
                observation(no_playback=0.003, remote_playback=0.003),
                "capture_path",
            ),
            (
                observation(no_playback=0.03, remote_playback=0.02),
                "server_vad_sensitivity",
            ),
            (
                observation(
                    no_playback=0.03,
                    remote_playback=0.003,
                    no_playback_vad=True,
                ),
                "full_duplex_attenuation",
            ),
            (
                observation(
                    no_playback=0.03,
                    remote_playback=0.02,
                    no_playback_vad=True,
                ),
                "server_vad_sensitivity",
            ),
            (
                observation(
                    no_playback=0.03,
                    remote_playback=0.02,
                    no_playback_vad=True,
                    remote_playback_vad=True,
                ),
                "event_orchestration",
            ),
            (
                observation(
                    no_playback=0.003,
                    remote_playback=0.02,
                    remote_playback_vad=True,
                ),
                "inconclusive",
            ),
            (
                observation(count=0),
                "inconclusive",
            ),
        )
        for candidate, expected in cases:
            with self.subTest(expected=expected):
                result = classify_diagnostic_observation(candidate)
                self.assertEqual(result["category"], expected)
                self.assertIn("diagnostic evidence only", result["interpretation"])
                self.assertTrue(result["support"]["cleanup_restored"])


class FakeDiagnosticHost:
    def __init__(self, *, emit_levels: bool = True, fail_start: bool = False) -> None:
        self.state = "wake_owned"
        self.mic_open = True
        self.events: list[dict[str, object]] = []
        self.at_ms = 0
        self.mode = "baseline"
        self.emit_levels = emit_levels
        self.fail_start = fail_start
        self.stop_calls = 0

    def add(self, event_type: str, **detail: object) -> None:
        self.at_ms += 100
        self.events.append(
            {
                "type": event_type,
                "at_ms": self.at_ms,
                "session_id": SESSION_ID,
                **detail,
            }
        )

    def play(self, _path: Path) -> None:
        if self.fail_start:
            self.add(
                "host_error",
                reason="webrtc_negotiation_failed",
                httpStatus=429,
                errorType="rate_limit_error",
                errorCode="rate_limit_exceeded",
                requestId="req_fake_f060",
                retryAfter="30",
            )
            return
        self.state = "host_active"
        self.mic_open = False
        self.add("host_connected")

    def announce(self, message: str) -> None:
        if "no answer playing" in message:
            self.mode = "no_playback_speech"
        elif "counting answer" in message:
            self.mode = "remote_playback_speech"

    def request(self, url: str, *, method: str = "GET") -> dict[str, object]:
        if url.endswith("/api/report"):
            if self.state == "host_active" and self.emit_levels:
                if self.mode == "baseline":
                    phase, rms = "no_remote_playback", 0.002
                elif self.mode == "no_playback_speech":
                    phase, rms = "no_remote_playback", 0.03
                else:
                    phase, rms = "remote_playback", 0.02
                self.add(
                    "host_input_level",
                    phase=phase,
                    rms=rms,
                    peak=rms * 2,
                    sampleCount=5,
                )
            return {
                "state": self.state,
                "wake_microphone_open": self.mic_open,
                "events": deepcopy(self.events),
            }
        if url.endswith("/api/long-answer"):
            self.add("host_response_created")
            return {"ok": True}
        if url.endswith("/api/stop"):
            self.stop_calls += 1
            self.state = "wake_owned"
            self.mic_open = True
            self.add("host_stopped", reason="explicit")
            return {"ok": True}
        raise AssertionError((url, method))


class AssistedDiagnosticRunnerTests(unittest.TestCase):
    def test_guided_runner_collects_both_phases_classifies_and_cleans_up(self):
        host = FakeDiagnosticHost()
        now = [0.0]
        with tempfile.TemporaryDirectory() as directory:
            wake = Path(directory) / "wake.wav"
            wake.write_bytes(b"fixture")
            runner = AssistedInputDiagnosisRunner(
                wake_fixture=wake,
                request=host.request,
                play=host.play,
                clock=lambda: now[0],
                sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
                baseline_seconds=0.3,
                speech_window_seconds=0.3,
                transition_timeout=1.0,
                announce=host.announce,
            )
            evidence = runner.run()
        self.assertEqual(evidence["feature_id"], "F060")
        self.assertEqual(evidence["result"]["category"], "server_vad_sensitivity")
        self.assertEqual(host.stop_calls, 1)
        self.assertTrue(evidence["result"]["support"]["cleanup_restored"])
        encoded = json.dumps(evidence)
        for forbidden in ("transcript", "audio_delta", "api_key", "client_secret"):
            self.assertNotIn(forbidden, encoded)

    def test_missing_level_capability_fails_with_bounded_cleanup_evidence(self):
        host = FakeDiagnosticHost(emit_levels=False)
        now = [0.0]
        with tempfile.TemporaryDirectory() as directory:
            wake = Path(directory) / "wake.wav"
            wake.write_bytes(b"fixture")
            runner = AssistedInputDiagnosisRunner(
                wake_fixture=wake,
                request=host.request,
                play=host.play,
                clock=lambda: now[0],
                sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
                baseline_seconds=0.2,
                transition_timeout=1.0,
                announce=lambda _message: None,
            )
            with self.assertRaisesRegex(
                RealtimeDiagnosisLiveFailure, "no browser input-level"
            ) as caught:
                runner.run()
        self.assertEqual(host.stop_calls, 1)
        self.assertEqual(caught.exception.evidence["result"]["failure_stage"], "silence_baseline")
        self.assertNotIn("transcript", json.dumps(caught.exception.evidence))

    def test_startup_host_error_fails_immediately_and_requests_cleanup(self):
        host = FakeDiagnosticHost(fail_start=True)
        now = [0.0]
        with tempfile.TemporaryDirectory() as directory:
            wake = Path(directory) / "wake.wav"
            wake.write_bytes(b"fixture")
            runner = AssistedInputDiagnosisRunner(
                wake_fixture=wake,
                request=host.request,
                play=host.play,
                clock=lambda: now[0],
                sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
                transition_timeout=30.0,
                announce=lambda _message: None,
            )
            with self.assertRaisesRegex(
                RealtimeDiagnosisLiveFailure, "host reported an error"
            ) as caught:
                runner.run()
        self.assertEqual(now[0], 0.0)
        self.assertEqual(host.stop_calls, 1)
        self.assertEqual(caught.exception.evidence["result"]["failure_stage"], "session_start")
        evidence_text = json.dumps(caught.exception.evidence)
        self.assertIn("rate_limit_exceeded", evidence_text)
        self.assertIn("req_fake_f060", evidence_text)

    def test_offline_cli_classifies_saved_sanitized_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observation.json"
            path.write_text(json.dumps(observation()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(["offline", str(path)])
        self.assertEqual(exit_code, 0)
        self.assertIn('"category": "server_vad_sensitivity"', output.getvalue())


if __name__ == "__main__":
    unittest.main()

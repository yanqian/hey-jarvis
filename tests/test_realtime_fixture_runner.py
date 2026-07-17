from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from src.realtime.fixture_runner import FixtureAcceptanceRunner, FixtureRunError


class FakeHost:
    def __init__(self, *, barge_reason: str = "cancelled", extra_speech: bool = False) -> None:
        self.state = "wake_owned"
        self.mic_open = True
        self.events: list[dict[str, object]] = []
        self.now = 0
        self.barge_reason = barge_reason
        self.extra_speech = extra_speech

    def add(self, event_type: str, **detail: object) -> None:
        self.now += 100
        self.events.append({"at_ms": self.now, "type": event_type, "session_id": "session-test", **detail})

    def request(self, url: str, *, method: str = "GET") -> dict[str, object]:
        if url.endswith("/api/report"):
            return {"state": self.state, "wake_microphone_open": self.mic_open, "events": list(self.events)}
        if url.endswith("/api/long-answer"):
            self.add("host_response_created")
            return {"ok": True}
        if url.endswith("/api/stop"):
            self.state = "wake_owned"
            self.mic_open = True
            return {"ok": True}
        raise AssertionError(url)

    def play(self, path: Path) -> None:
        if path.name == "wake.wav":
            self.state = "host_active"
            self.mic_open = False
            self.add("host_connected")
            return
        self.add("host_speech_started")
        if path.name == "barge-in.wav":
            self.add("host_response_done", reason=self.barge_reason)
            self.add("host_speech_stopped")
            self.add("host_response_created")
            self.add("host_response_done", reason="completed")
        elif path.name == "calculator.wav":
            self.add("host_speech_stopped")
            self.add("host_response_created")
            self.add("host_tool_call", result="completed")
            self.add("host_response_done", reason="completed")
            self.add("host_response_created")
            self.add("host_response_done", reason="completed")
        elif path.name == "end-phrase.wav":
            self.add("host_speech_stopped")
            self.add("host_transcription")
            self.add("host_end_phrase_matched")
            self.add("host_stopped", reason="end_phrase")
            self.state = "wake_owned"
            self.mic_open = True
            self.add("wake_microphone_reopened")
        else:
            self.add("host_speech_stopped")
            self.add("host_response_created")
            self.add("host_response_done", reason="completed")
            if self.extra_speech and path.name == "turn-1.wav":
                self.add("host_speech_started")


class FixtureRunnerTests(unittest.TestCase):
    def run_host(self, host: FakeHost):
        runner = FixtureAcceptanceRunner(play=host.play, request=host.request, sleep=lambda _seconds: None)
        with patch("src.realtime.fixture_runner.load_manifest", return_value={name: object() for name in ("wake", "turn-1", "turn-2", "calculator", "barge-in", "end-phrase")}):
            return runner.run()

    def test_requires_two_completed_turns_cancelled_barge_and_wake_recovery(self):
        result = self.run_host(FakeHost())
        self.assertEqual(result["turns_completed"], 6)
        self.assertEqual(result["speech_started"], 5)
        self.assertEqual(result["barge_in_cancel_latency_ms"], 100)
        self.assertEqual(result["calculator_calls"], 1)
        self.assertEqual(result["end_phrase_matches"], 1)
        self.assertTrue(result["recovered_to_wake"])

    def test_rejects_naturally_completed_barge_in_response(self):
        with self.assertRaisesRegex(FixtureRunError, "barge-in response.done"):
            self.run_host(FakeHost(barge_reason="completed"))

    def test_rejects_unexpected_speech_start_outside_the_five_fixtures(self):
        with self.assertRaisesRegex(FixtureRunError, "unexpected speech_started count"):
            self.run_host(FakeHost(extra_speech=True))


if __name__ == "__main__":
    unittest.main()

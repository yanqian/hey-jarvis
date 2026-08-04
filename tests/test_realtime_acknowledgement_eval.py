from __future__ import annotations

import unittest

from src.evals.realtime_acknowledgement import AcknowledgementABRunner, evaluate_observation
from src.evals.realtime_common import RealtimeRunFailure, RealtimeScenarioError


def event(event_type: str, at_ms: int, **detail: object) -> dict[str, object]:
    return {"type": event_type, "at_ms": at_ms, **detail}


def observation() -> dict[str, object]:
    return {
        "configuration": {
            "model": "gpt-realtime",
            "voice": "alloy",
            "output_volume": 0.5,
            "host": "same_loopback_host",
        },
        "trials": [
            {
                "mode": "local",
                "events": [
                    event("wake_confirmed", 0),
                    event("host_session_configured", 1000, session_id="local-session"),
                    event("ack_started", 1010, ack_asset_duration_ms=480),
                    event("ack_completed", 1500),
                    event("host_connected", 1510, session_id="local-session"),
                    event("host_stopped", 2000, session_id="local-session"),
                    event("wake_microphone_reopened", 2010, session_id="local-session"),
                ],
            },
            {
                "mode": "realtime",
                "events": [
                    event("wake_confirmed", 3000),
                    event("host_session_configured", 4000, session_id="remote-session"),
                    event("host_realtime_ack_response_created", 4200, session_id="remote-session"),
                    event("host_realtime_ack_playback_started", 4300, session_id="remote-session"),
                    event(
                        "host_realtime_ack_response_done",
                        4600,
                        session_id="remote-session",
                        reason="completed",
                    ),
                    event("host_realtime_ack_playback_stopped", 4700, session_id="remote-session"),
                    event("host_connected", 4710, session_id="remote-session"),
                    event("host_stopped", 5000, session_id="remote-session"),
                    event("wake_microphone_reopened", 5010, session_id="remote-session"),
                ],
            },
        ],
        "perceptual_verdict": "realtime",
    }


class RealtimeAcknowledgementEvalTests(unittest.TestCase):
    def test_offline_oracle_separates_timings_without_acoustic_claim(self):
        result = evaluate_observation(observation())
        self.assertEqual(result["result"], "passed")
        self.assertEqual(result["input_ready_delta_ms"], 200)
        self.assertEqual(result["timing_ms"]["local"]["ack_asset_duration_ms"], 480)
        self.assertIsNone(result["timing_ms"]["realtime"]["ack_asset_duration_ms"])
        self.assertEqual(result["timing_ms"]["local"]["playback_path"], "local_asset_player")
        self.assertEqual(result["timing_ms"]["realtime"]["playback_path"], "remote_webrtc_audio")
        self.assertFalse(result["latency_slo_claimed"])
        self.assertEqual(result["recommendation"], "consider_realtime_for_voice_consistency")

    def test_privacy_oracle_rejects_transcript_or_provider_payload(self):
        for forbidden in ("transcript", "provider_payload"):
            candidate = observation()
            candidate[forbidden] = "private"
            with self.subTest(forbidden=forbidden), self.assertRaisesRegex(
                RealtimeScenarioError, "forbidden private field"
            ):
                evaluate_observation(candidate)

    def test_realtime_trial_rejects_input_before_playback_completion(self):
        candidate = observation()
        candidate["trials"][1]["events"][6]["at_ms"] = 4650
        with self.assertRaisesRegex(RealtimeScenarioError, "misordered"):
            evaluate_observation(candidate)

    def test_inconclusive_verdict_does_not_force_a_switch(self):
        candidate = observation()
        candidate["perceptual_verdict"] = "inconclusive"
        self.assertEqual(evaluate_observation(candidate)["recommendation"], "inconclusive")

    def test_operator_cancellation_attempts_bounded_cleanup(self):
        calls: list[tuple[str, str]] = []

        def request(url: str, *, method: str = "GET") -> dict[str, object]:
            calls.append((url, method))
            if url.endswith("/api/realtime-settings"):
                raise KeyboardInterrupt
            return {"status": "stopping"}

        runner = AcknowledgementABRunner(
            scenario_id="ACK-AB",
            base_url="http://127.0.0.1:8770",
            wake_fixture=None,
            request=request,
        )
        with self.assertRaises(RealtimeRunFailure) as raised:
            runner.run(verdict="inconclusive")
        self.assertEqual(raised.exception.evidence["result"]["result"], "failed")
        self.assertIn(("http://127.0.0.1:8770/api/stop", "POST"), calls)

    def test_retry_can_reuse_only_a_complete_sanitized_local_trial(self):
        source = observation()["trials"][0]
        report = {
            "state": "wake_owned",
            "wake_microphone_open": True,
            "events": source["events"],
        }
        reused = AcknowledgementABRunner._latest_complete_local_trial(report)
        self.assertEqual(reused["mode"], "local")
        self.assertNotIn("session_id", str(reused))
        self.assertEqual(
            next(event for event in reused["events"] if event["type"] == "ack_started")[
                "ack_asset_duration_ms"
            ],
            480,
        )

    def test_retry_can_validate_a_saved_sanitized_local_trial(self):
        source = observation()["trials"][0]
        runner = AcknowledgementABRunner(
            scenario_id="ACK-AB",
            base_url="http://127.0.0.1:8770",
            wake_fixture=None,
            request=lambda *_args, **_kwargs: {},
        )
        self.assertEqual(runner._sanitize_trial("local", source["events"], {})["mode"], "local")
        self.assertEqual(
            evaluate_observation({**observation(), "trials": [source, observation()["trials"][1]]})[
                "result"
            ],
            "passed",
        )


if __name__ == "__main__":
    unittest.main()

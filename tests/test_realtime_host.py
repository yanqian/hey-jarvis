from __future__ import annotations

import json
import unittest

from src.realtime_host.coordinator import (
    MAX_TOOL_ARGUMENT_CHARS,
    HandoffCoordinator,
    HandoffError,
    HandoffState,
)
from src.realtime_host import server


class FakeLease:
    def __init__(self) -> None:
        self.is_open = False
        self.calls: list[str] = []

    def open(self) -> None:
        self.calls.append("open")
        self.is_open = True

    def close(self) -> None:
        self.calls.append("close")
        self.is_open = False


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class RealtimeHostTests(unittest.TestCase):
    def build_coordinator(self):
        lease = FakeLease()
        ids = iter(f"session-{index}" for index in range(10))
        coordinator = HandoffCoordinator(lease, clock=lambda: 1.25, session_ids=lambda: next(ids))
        return coordinator, lease

    def test_host_requires_one_arm_then_preserves_exclusive_order_for_five_cycles(self):
        coordinator, lease = self.build_coordinator()
        with self.assertRaisesRegex(HandoffError, "armed"):
            coordinator.begin_handoff()
        coordinator.host_event("armed")
        cursor = 0
        for _ in range(5):
            session_id = coordinator.begin_handoff()
            self.assertFalse(lease.is_open)
            start = coordinator.command_after(cursor)
            self.assertEqual(start["type"], "start")
            cursor = start["command_id"]
            coordinator.host_event("microphone_requested", session_id)
            coordinator.host_event("microphone_acquired", session_id, echoCancellation=True)
            coordinator.host_event("connected", session_id)
            self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)
            coordinator.request_long_answer()
            long_answer = coordinator.command_after(cursor)
            self.assertEqual(long_answer["type"], "long_answer")
            cursor = long_answer["command_id"]
            coordinator.request_stop()
            stop = coordinator.command_after(cursor)
            self.assertEqual(stop["type"], "stop")
            cursor = stop["command_id"]
            coordinator.host_event("stopped", session_id, reason="test")
            self.assertTrue(lease.is_open)
            self.assertEqual(coordinator.state, HandoffState.WAKE_OWNED)
        self.assertEqual(lease.calls, ["open"] + [call for _ in range(5) for call in ("close", "open")])
        types = [event["type"] for event in coordinator.report()["events"]]
        self.assertLess(types.index("wake_microphone_closed"), types.index("host_microphone_requested"))

    def test_only_the_armed_browser_instance_can_consume_commands_or_emit_events(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
        coordinator.host_event("armed", host_id="host-current")
        session_id = coordinator.begin_handoff()
        self.assertIsNone(coordinator.command_after(0, host_id="host-stale"))
        self.assertEqual(coordinator.command_after(0, host_id="host-current")["type"], "start")
        with self.assertRaisesRegex(HandoffError, "armed host"):
            coordinator.host_event("connected", session_id, host_id="host-stale")
        coordinator.host_event("connected", session_id, host_id="host-current")
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_real_wake_lease_can_wait_until_browser_arm_warmup_finishes(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(lease, open_wake_on_init=False)
        self.assertFalse(lease.is_open)
        coordinator.host_event("armed")
        self.assertTrue(lease.is_open)
        self.assertEqual(lease.calls, ["open"])
        types = [event["type"] for event in coordinator.report()["events"]]
        self.assertEqual(types[:3], ["wake_microphone_deferred_until_arm", "wake_microphone_opened", "host_armed"])

    def test_stale_events_fail_and_error_waits_for_media_stop_before_reopening(self):
        coordinator, lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        with self.assertRaisesRegex(HandoffError, "active session"):
            coordinator.host_event("connected", "stale")
        coordinator.host_event("error", session_id, reason="permission_denied")
        self.assertFalse(lease.is_open)
        self.assertEqual(coordinator.state, HandoffState.HOST_STOPPING)
        coordinator.host_event("stopped", session_id, reason="error_cleanup")
        self.assertTrue(lease.is_open)
        self.assertEqual(coordinator.state, HandoffState.WAKE_OWNED)

    def test_completed_transcription_matches_only_exact_bilingual_end_utterances(self):
        for transcript in (
            " 再见。 ",
            "GOODBYE!",
            "good bye.",
            "结束对话",
            "结束 对话。",
            "end   conversation...",
        ):
            with self.subTest(transcript=transcript):
                lease = FakeLease()
                coordinator = HandoffCoordinator(
                    lease,
                    session_ids=lambda: "session-end",
                    end_phrases=("再见", "goodbye", "结束对话", "end conversation"),
                )
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                coordinator.host_event("connected", session_id)
                result = coordinator.host_event(
                    "transcription", session_id, item_id="item-1", transcript=transcript
                )
                self.assertEqual(result, "stopping")
                self.assertEqual(coordinator.state, HandoffState.HOST_STOPPING)
                report_text = json.dumps(coordinator.report(), ensure_ascii=False)
                self.assertNotIn(transcript.strip(), report_text)
                self.assertNotIn("GOODBYE", report_text)

    def test_transcription_false_positives_duplicates_failures_and_late_events_are_safe(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(
            lease,
            session_ids=lambda: "session-1",
            end_phrases=("再见", "goodbye"),
        )
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event("connected", session_id)
        for index, transcript in enumerate(("", "goodbye for now please", "please say goodbye", "取消", "再见北京")):
            self.assertEqual(
                coordinator.host_event(
                    "transcription", session_id, item_id=f"item-{index}", transcript=transcript
                ),
                "accepted",
            )
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)
        self.assertEqual(
            coordinator.host_event("transcription", session_id, item_id="item-4", transcript="再见"),
            "accepted",
        )
        coordinator.host_event("transcription_failed", session_id, item_id="item-failed")
        coordinator.host_event("response_created", session_id)
        coordinator.request_stop("explicit")
        self.assertEqual(
            coordinator.host_event("transcription", session_id, item_id="item-late", transcript="再见"),
            "stopping",
        )
        self.assertFalse(lease.is_open)
        coordinator.host_event("stopped", session_id)
        self.assertTrue(lease.is_open)
        report_text = json.dumps(coordinator.report(), ensure_ascii=False)
        for transcript in ("goodbye for now please", "please say goodbye", "取消", "再见北京"):
            self.assertNotIn(transcript, report_text)

    def test_missing_item_text_and_long_completed_transcripts_never_close(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1", end_phrases=("goodbye",))
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event("connected", session_id)
        for detail in (
            {"transcript": "goodbye"},
            {"item_id": "item-empty", "transcript": "  "},
            {"item_id": "item-long", "transcript": "x" * 201},
            {"item_id": "item-not-short", "transcript": "goodbye " + "please " * 10},
        ):
            self.assertEqual(coordinator.host_event("transcription", session_id, **detail), "accepted")
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_realtime_calculator_uses_safe_existing_tool_and_enqueues_one_output(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event("connected", session_id)
        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="call-1",
            name="calculator",
            arguments=json.dumps({"expression": "(2 + 3) * 4"}),
        )
        command = coordinator.command_after(1)
        self.assertEqual(command["type"], "tool_result")
        self.assertEqual(command["call_id"], "call-1")
        self.assertEqual(json.loads(command["output"]), {"status": "success", "answer": "The answer is 20."})
        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="call-1",
            name="calculator",
            arguments=json.dumps({"expression": "999"}),
        )
        self.assertIsNone(coordinator.command_after(command["command_id"]))

    def test_realtime_calculator_malformed_unsafe_and_unknown_calls_return_safe_errors(self):
        cases = (
            ("calculator", "not-json", "Calculator arguments were invalid."),
            ("calculator", json.dumps({"expression": "__import__('os')"}), "I could not safely calculate"),
            ("weather", json.dumps({"expression": "2+2"}), "Unsupported Realtime tool."),
        )
        for index, (name, arguments, expected) in enumerate(cases):
            with self.subTest(name=name, arguments=arguments):
                lease = FakeLease()
                coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                coordinator.host_event("connected", session_id)
                coordinator.host_event(
                    "tool_call", session_id, call_id=f"call-{index}", name=name, arguments=arguments
                )
                output = json.loads(coordinator.command_after(1)["output"])
                self.assertEqual(output["status"], "error")
                self.assertIn(expected, output["answer"])
                self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_end_conversation_tool_requests_one_existing_stop_without_output(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event("connected", session_id)

        result = coordinator.host_event(
            "tool_call",
            session_id,
            call_id="end-call",
            name="end_conversation",
            arguments="{}",
        )

        self.assertEqual(result, "stopping")
        self.assertEqual(coordinator.state, HandoffState.HOST_STOPPING)
        command = coordinator.command_after(1)
        self.assertEqual(command["type"], "stop")
        self.assertEqual(command["reason"], "end_phrase")
        self.assertNotIn("output", command)
        self.assertEqual(
            coordinator.host_event(
                "tool_call",
                session_id,
                call_id="end-call",
                name="end_conversation",
                arguments="{}",
            ),
            "stopping",
        )
        self.assertIsNone(coordinator.command_after(command["command_id"]))
        report_text = json.dumps(coordinator.report())
        self.assertIn("host_end_conversation_tool", report_text)
        for private in ("end-call", "arguments"):
            self.assertNotIn(private, report_text)

    def test_end_conversation_tool_rejects_nonempty_or_malformed_arguments(self):
        for index, arguments in enumerate(
            (
                "not-json",
                "[]",
                json.dumps({"reason": "goodbye"}),
                " " * (MAX_TOOL_ARGUMENT_CHARS + 1),
            )
        ):
            with self.subTest(arguments=arguments):
                lease = FakeLease()
                coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                coordinator.host_event("connected", session_id)
                result = coordinator.host_event(
                    "tool_call",
                    session_id,
                    call_id=f"bad-end-{index}",
                    name="end_conversation",
                    arguments=arguments,
                )
                self.assertEqual(result, "accepted")
                self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)
                self.assertIsNone(coordinator.command_after(1))
                report_text = json.dumps(coordinator.report())
                self.assertIn("host_end_conversation_tool_ignored", report_text)
                self.assertNotIn(arguments, report_text)

    def test_fixture_audio_is_bounded_session_scoped_and_excluded_from_report(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event("connected", session_id)
        encoded = "AQACAA=="
        coordinator.request_fixture_audio("turn-1", encoded)
        command = coordinator.command_after(1)
        self.assertEqual(command["type"], "fixture_audio")
        self.assertEqual(command["fixture_name"], "turn-1")
        self.assertEqual(command["audio"], encoded)
        report_text = json.dumps(coordinator.report())
        self.assertNotIn(encoded, report_text)
        with self.assertRaisesRegex(HandoffError, "name"):
            coordinator.request_fixture_audio("wake", encoded)
        with self.assertRaisesRegex(HandoffError, "payload"):
            coordinator.request_fixture_audio("turn-2", "not-base64")

    def test_invalid_generated_session_does_not_release_wake_microphone(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(lease, session_ids=lambda: "invalid session id")
        coordinator.host_event("armed")
        with self.assertRaisesRegex(HandoffError, "identity"):
            coordinator.begin_handoff()
        self.assertTrue(lease.is_open)
        self.assertEqual(coordinator.state, HandoffState.WAKE_OWNED)

    def test_static_host_is_separate_hands_free_and_secret_free(self):
        html = server.resolve_static("/")[0].decode()
        javascript = server.resolve_static("/app.js")[0].decode()
        guidance = (server.STATIC_ROOT.parent / "README.md").read_text()
        self.assertIn("Arm hands-free audio", html)
        for text in ("getUserMedia", "/api/command?after=", "host_id", "echoCancellation:true", "track.stop()", "peer.close()"):
            self.assertIn(text, javascript)
        self.assertIn("REMOTE_AUDIO_VOLUME=0.1", javascript)
        self.assertIn("threshold:sessionConfig.server_vad_threshold", javascript)
        self.assertIn("sessionConfig.output_volume", javascript)
        for text in (
            "createMediaStreamSource(mediaStream)",
            "getFloatTimeDomainData",
            'assistantSpeaking?"remote_playback":"no_remote_playback"',
            'hostEvent("input_level"',
            "INPUT_LEVEL_WINDOW_SAMPLES=5",
            "stopInputLevels()",
            "webrtc_negotiation_failed",
            'response.headers.get("x-request-id")',
            'response.headers.get("retry-after")',
            'response.headers.get("x-ratelimit-remaining-requests")',
            'response.headers.get("x-ratelimit-reset-requests")',
            "error.safeDiagnostic=detail",
            'type:"input_audio"',
            'hostEvent("fixture_submitted")',
            'command.type==="fixture_audio"',
            "handoffTimingSummary",
            'hostEvent("handoff_timing"',
            "command_to_token_ms",
            "token_ms",
            "microphone_ms",
            "peer_setup_ms",
            "microphone_reporting_ms",
            "audio_analysis_setup_ms",
            "peer_connection_setup_ms",
            "offer_creation_ms",
            "local_description_ms",
            "negotiation_ms",
            "session_configuration_ms",
            "total_browser_ready_ms",
        ):
            self.assertIn(text, javascript)
        self.assertNotIn("JSON.stringify(payload)", javascript.split("async function negotiationFailure", 1)[1].split("function flushInputLevels", 1)[0])
        for text in ('type:"server_vad"', "create_response:true", "interrupt_response:true", 'event.type==="session.updated"'):
            self.assertIn(text, javascript)
        for text in (
            'name:"calculator"',
            'name:"end_conversation"',
            "# Language",
            "language primarily used in the user's current utterance",
            "concise, natural Simplified Chinese",
            "For English input, answer in English",
            "current user utterance overrides prior turns",
            "English tool definitions, and English tool outputs",
            "mixed or ambiguous input",
            "translation, spelling, pronunciation, language practice",
            "surrounding explanation in the language of the current request",
            "clearly and unambiguously wants to end",
            "do not provide a spoken or substantive response",
            "async function forwardToolCall",
            'result.status==="stopping"',
            'await stop("end_phrase")',
            'response.function_call_arguments.done',
            'item.type==="function_call"',
            'type:"function_call_output"',
        ):
            self.assertIn(text, javascript)
        for forbidden_tool in ('name:"weather"', 'name:"stock"', 'name:"fx"'):
            self.assertNotIn(forbidden_tool, javascript)
        self.assertNotIn("transcript decides", javascript)
        for forbidden in ("response.cancel", "conversation.item.truncate", "output_audio_buffer.clear"):
            self.assertNotIn(forbidden, javascript)
        self.assertNotIn("OPENAI_API_KEY", javascript)
        self.assertIn("without another browser click", guidance)
        self.assertIn("five start/stop cycles", guidance)

    def test_loopback_and_token_redaction(self):
        with self.assertRaisesRegex(server.HostServerError, "loopback"):
            server.build_server("0.0.0.0", 0)
        result = server.mint_client_secret(
            api_key="sk-fake-standard",
            model="model-test",
            voice="marin",
            urlopen=lambda *_args, **_kwargs: FakeResponse({"value": "ek_test", "secret": "ignored"}),
        )
        self.assertEqual(result, {"value": "ek_test", "model": "model-test", "voice": "marin"})
        self.assertNotIn("sk-fake-standard", json.dumps(result))

    def test_report_is_bounded_and_redacts_content_and_tool_secrets(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event("connected", session_id)
        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="call-secret",
            name="calculator",
            arguments=json.dumps({"expression": "2 + 2"}),
        )
        coordinator.host_event(
            "response_done",
            session_id,
            reason="sk-secret ek_secret raw transcript c2VjcmV0 audio delta",
        )
        for _ in range(250):
            coordinator.host_event("response_created", session_id)

        report = coordinator.report()
        report_text = json.dumps(report)
        self.assertLessEqual(len(report["events"]), 200)
        for secret in ("call-secret", "The answer is 4", "sk-secret", "ek_secret", "raw transcript", "c2VjcmV0"):
            self.assertNotIn(secret, report_text)

    def test_input_level_events_are_strictly_validated_rounded_and_bounded(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event("connected", session_id)
        coordinator.host_event(
            "input_level",
            session_id,
            phase="no_remote_playback",
            rms=0.012345,
            peak=0.234567,
            sampleCount=5,
            transcript="must-not-survive",
        )
        level = next(
            event
            for event in coordinator.report()["events"]
            if event["type"] == "host_input_level"
        )
        self.assertEqual(
            level,
            {
                "at_ms": 1250,
                "type": "host_input_level",
                "session_id": session_id,
                "phase": "no_remote_playback",
                "rms": 0.0123,
                "peak": 0.2346,
                "sampleCount": 5,
            },
        )
        self.assertNotIn("transcript", json.dumps(coordinator.report()))

        invalid_details = (
            {"phase": "unknown", "rms": 0.1, "peak": 0.2, "sampleCount": 5},
            {"phase": "remote_playback", "rms": -0.1, "peak": 0.2, "sampleCount": 5},
            {"phase": "remote_playback", "rms": 0.1, "peak": 1.1, "sampleCount": 5},
            {"phase": "remote_playback", "rms": 0.1, "peak": 0.2, "sampleCount": 0},
            {"phase": "remote_playback", "rms": True, "peak": 0.2, "sampleCount": 5},
        )
        for detail in invalid_details:
            with self.subTest(detail=detail), self.assertRaisesRegex(HandoffError, "Input-level"):
                coordinator.host_event("input_level", session_id, **detail)

    def test_handoff_timing_is_complete_bounded_private_and_single_shot(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        coordinator.record_local_timing_marker("wake_confirmed")
        coordinator.record_local_timing_marker("ack_started")
        coordinator.record_local_timing_marker("ack_completed")
        session_id = coordinator.begin_handoff()
        timing = {
            "command_to_token_ms": 4,
            "token_ms": 200,
            "microphone_ms": 300,
            "peer_setup_ms": 20,
            "microphone_reporting_ms": 2,
            "audio_analysis_setup_ms": 1,
            "peer_connection_setup_ms": 4,
            "offer_creation_ms": 5,
            "local_description_ms": 8,
            "negotiation_ms": 900,
            "session_configuration_ms": 100,
            "total_browser_ready_ms": 1524,
        }
        coordinator.host_event(
            "handoff_timing",
            session_id,
            **timing,
        )
        recorded = next(
            event
            for event in coordinator.report()["events"]
            if event["type"] == "host_handoff_timing"
        )
        self.assertEqual({field: recorded[field] for field in timing}, timing)
        report_text = json.dumps(coordinator.report())
        self.assertNotIn('"transcript":', report_text)
        self.assertNotIn('"token":', report_text)
        with self.assertRaisesRegex(HandoffError, "already reported"):
            coordinator.host_event("handoff_timing", session_id, **timing)
        with self.assertRaisesRegex(HandoffError, "Local timing marker"):
            coordinator.record_local_timing_marker("private_marker")

        invalid = (
            ({key: value for key, value in timing.items() if key != "token_ms"}, "incomplete"),
            ({**timing, "transcript": "private", "token": "secret"}, "unsupported"),
            ({**timing, "token_ms": -1}, "outside"),
            ({**timing, "token_ms": True}, "integer"),
            ({**timing, "total_browser_ready_ms": 1}, "match"),
            ({**timing, "local_description_ms": 40}, "subphases"),
        )
        for detail, expected in invalid:
            with self.subTest(expected=expected):
                other, _other_lease = self.build_coordinator()
                other.host_event("armed")
                other_session = other.begin_handoff()
                with self.assertRaisesRegex(HandoffError, expected):
                    other.host_event("handoff_timing", other_session, **detail)

    def test_negotiation_error_retains_only_strict_safe_metadata(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event(
            "error",
            session_id,
            reason="webrtc_negotiation_failed",
            httpStatus=429,
            errorType="insufficient_quota",
            errorCode="insufficient_quota",
            requestId="req_safe_123",
            retryAfter="60",
            rateLimitRemainingRequests="0",
            rateLimitResetRequests="1m0s",
            responseBody='{"api_key":"sk-secret"}',
            transcript="private utterance",
        )
        error = next(
            event for event in coordinator.report()["events"] if event["type"] == "host_error"
        )
        self.assertEqual(
            error,
            {
                "at_ms": 1250,
                "type": "host_error",
                "session_id": session_id,
                "reason": "webrtc_negotiation_failed",
                "httpStatus": 429,
                "errorType": "insufficient_quota",
                "errorCode": "insufficient_quota",
                "requestId": "req_safe_123",
                "retryAfter": "60",
                "rateLimitRemainingRequests": "0",
                "rateLimitResetRequests": "1m0s",
            },
        )
        report_text = json.dumps(coordinator.report())
        self.assertNotIn("sk-secret", report_text)
        self.assertNotIn("private utterance", report_text)
        self.assertEqual(coordinator.state, HandoffState.HOST_STOPPING)

        coordinator2, _lease2 = self.build_coordinator()
        coordinator2.host_event("armed")
        session_id2 = coordinator2.begin_handoff()
        with self.assertRaisesRegex(HandoffError, "Negotiation"):
            coordinator2.host_event(
                "error",
                session_id2,
                reason="webrtc_negotiation_failed",
                httpStatus=429,
                errorCode="unsafe value with spaces",
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import unittest

from src.realtime_host.coordinator import HandoffCoordinator, HandoffError, HandoffState
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
        for text in ('type:"server_vad"', "create_response:true", "interrupt_response:true", 'event.type==="session.updated"'):
            self.assertIn(text, javascript)
        for text in (
            'name:"calculator"',
            'response.function_call_arguments.done',
            'item.type==="function_call"',
            'type:"function_call_output"',
        ):
            self.assertIn(text, javascript)
        for forbidden_tool in ('name:"weather"', 'name:"stock"', 'name:"fx"'):
            self.assertNotIn(forbidden_tool, javascript)
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


if __name__ == "__main__":
    unittest.main()

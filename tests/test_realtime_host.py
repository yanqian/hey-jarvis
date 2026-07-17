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
        for text in ("getUserMedia", "/api/command?after=", "echoCancellation:true", "track.stop()", "peer.close()"):
            self.assertIn(text, javascript)
        for text in ('type:"server_vad"', "create_response:true", "interrupt_response:true", 'event.type==="session.updated"'):
            self.assertIn(text, javascript)
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


if __name__ == "__main__":
    unittest.main()

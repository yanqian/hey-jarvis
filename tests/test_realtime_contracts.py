from __future__ import annotations

import unittest

from src.realtime import (
    BridgeError,
    FakeClock,
    FakeRealtimeHost,
    HostCommandType,
    HostEventType,
    LoopbackBridge,
    RealtimeLifecycle,
)


class RealtimeContractTests(unittest.TestCase):
    def test_fake_clock_host_and_full_typed_event_surface(self):
        clock = FakeClock(10.0)
        bridge = LoopbackBridge(clock=clock)
        host = FakeRealtimeHost(bridge)
        host.ready()
        start = bridge.start("session-1", {"model": "gpt-realtime-2.1"})
        self.assertEqual(start.type, HostCommandType.START)
        self.assertEqual(bridge.lifecycle, RealtimeLifecycle.CONNECTING)

        host.connect("session-1")
        self.assertEqual(bridge.lifecycle, RealtimeLifecycle.ACTIVE_SESSION)
        for event_type in (
            HostEventType.VAD,
            HostEventType.RESPONSE,
            HostEventType.TRANSCRIPTION,
            HostEventType.TOOL_CALL,
        ):
            clock.advance(0.25)
            bridge.receive(event_type, "session-1", {"status": "bounded"})
        self.assertEqual(
            [event.type for event in bridge.events],
            [
                HostEventType.READY,
                HostEventType.CONNECTED,
                HostEventType.VAD,
                HostEventType.RESPONSE,
                HostEventType.TRANSCRIPTION,
                HostEventType.TOOL_CALL,
            ],
        )
        close = bridge.close("session-1", {"reason": "idle"})
        self.assertEqual(close.type, HostCommandType.CLOSE)
        self.assertEqual(bridge.lifecycle, RealtimeLifecycle.CLOSING)
        host.close("session-1")
        self.assertEqual(bridge.lifecycle, RealtimeLifecycle.WAIT_WAKE)
        self.assertIsNone(bridge.active_session_id)
        self.assertEqual(bridge.shutdown().type, HostCommandType.SHUTDOWN)

    def test_bridge_is_loopback_single_session_and_rejects_stale_identity(self):
        with self.assertRaisesRegex(BridgeError, "loopback"):
            LoopbackBridge("0.0.0.0")
        bridge = LoopbackBridge()
        with self.assertRaisesRegex(BridgeError, "not ready"):
            bridge.start("current")
        bridge.receive(HostEventType.READY, None)
        bridge.start("current")
        with self.assertRaisesRegex(BridgeError, "already active"):
            bridge.start("second")
        with self.assertRaisesRegex(BridgeError, "stale"):
            bridge.receive(HostEventType.CONNECTED, "stale")
        with self.assertRaisesRegex(BridgeError, "malformed"):
            bridge.close("invalid session id")
        with self.assertRaisesRegex(BridgeError, "malformed"):
            secret_bridge = LoopbackBridge()
            secret_bridge.receive(HostEventType.READY, None)
            secret_bridge.start("sk-secret-shaped-session")

    def test_bridge_rejects_raw_audio_secrets_malformed_and_oversized_payloads(self):
        bridge = LoopbackBridge()
        bridge.receive(HostEventType.READY, None)
        with self.assertRaisesRegex(BridgeError, "audio or secret"):
            bridge.start("s1", {"pcm": "AAAA"})
        with self.assertRaisesRegex(BridgeError, "secret-bearing"):
            bridge.start("s1", {"value": "sk-not-a-real-key"})
        with self.assertRaisesRegex(BridgeError, "bounded size|oversized"):
            bridge.start("s1", {"message": "x" * 5000})
        with self.assertRaisesRegex(BridgeError, "non-JSON"):
            bridge.start("s1", {"data": b"raw"})
        bridge.start("s1")
        with self.assertRaisesRegex(BridgeError, "Unknown"):
            bridge.receive("made_up", "s1")
        with self.assertRaisesRegex(BridgeError, "requires an active"):
            bridge.receive(HostEventType.RESPONSE, "s1")
        self.assertEqual([event.type for event in bridge.events], [HostEventType.READY])

    def test_error_event_returns_to_wait_wake(self):
        bridge = LoopbackBridge()
        bridge.receive(HostEventType.READY, None)
        bridge.start("s1")
        bridge.receive(HostEventType.ERROR, "s1", {"reason": "network"})
        self.assertEqual(bridge.lifecycle, RealtimeLifecycle.WAIT_WAKE)
        self.assertIsNone(bridge.active_session_id)


if __name__ == "__main__":
    unittest.main()

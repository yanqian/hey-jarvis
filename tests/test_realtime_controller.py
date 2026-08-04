from __future__ import annotations

import unittest

from src.realtime.controller import RealtimeSessionController
from src.realtime_host.coordinator import HandoffCoordinator, HandoffState


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeLease:
    def __init__(self, chunks: list[bytes]) -> None:
        self.is_open = False
        self.chunks = list(chunks)
        self.calls: list[str] = []

    def open(self) -> None:
        self.is_open = True
        self.calls.append("open")

    def close(self) -> None:
        self.is_open = False
        self.calls.append("close")

    def read_chunk(self) -> bytes:
        if not self.is_open:
            raise RuntimeError("read while closed")
        return self.chunks.pop(0)


class FakeDetector:
    def __init__(self) -> None:
        self.reset_calls = 0

    def detect(self, chunk: bytes) -> bool:
        return chunk == b"wake"

    def reset(self) -> None:
        self.reset_calls += 1


def build_runtime():
    clock = FakeClock()
    lease = FakeLease([b"quiet", b"wake", b"wake"])
    coordinator = HandoffCoordinator(lease, clock=clock, session_ids=lambda: "session-1")
    coordinator.host_event("armed")
    detector = FakeDetector()
    return clock, lease, coordinator, detector


class RealtimeControllerTests(unittest.TestCase):
    def test_wake_requires_consecutive_confirmations(self):
        clock = FakeClock()
        lease = FakeLease([b"wake", b"quiet", b"wake", b"wake"])
        coordinator = HandoffCoordinator(lease, clock=clock, session_ids=lambda: "session-1")
        coordinator.host_event("armed")

        def sleep(seconds: float) -> None:
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_READY:
                coordinator.host_event("connected", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_ACTIVE:
                coordinator.request_stop("test")
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id)

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=FakeDetector(),
            play_acknowledgement=lambda: None,
            idle_timeout_seconds=1.0,
            max_duration_seconds=2.0,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertTrue(result.recovered_to_wake)
        self.assertEqual(lease.chunks, [])

    def test_wake_ack_two_followup_turns_idle_close_and_fresh_wake(self):
        clock, lease, coordinator, detector = build_runtime()
        acknowledgements: list[str] = []
        active_polls = 0

        def play_ack() -> None:
            self.assertFalse(lease.is_open)
            acknowledgements.append("played")
            clock.advance(0.35)

        def sleep(seconds: float) -> None:
            nonlocal active_polls
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                session_id = coordinator.session_id
                coordinator.host_event("transport_connected", session_id)
                coordinator.host_event("session_created", session_id)
                coordinator.host_event("session_configured", session_id)
            elif coordinator.state == HandoffState.HOST_READY:
                coordinator.host_event("connected", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_ACTIVE:
                active_polls += 1
                if active_polls == 1:
                    for _ in range(2):
                        coordinator.host_event("speech_started", coordinator.session_id)
                        coordinator.host_event("speech_stopped", coordinator.session_id)
                        coordinator.host_event("response_created", coordinator.session_id)
                        coordinator.host_event("response_done", coordinator.session_id, reason="completed")
                    self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)
                    clock.advance(2.0)
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id, reason="python_stop")

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=play_ack,
            acknowledgement_duration_ms=200,
            idle_timeout_seconds=1.0,
            max_duration_seconds=30.0,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertEqual(acknowledgements, ["played"])
        self.assertEqual(active_polls, 1)
        self.assertEqual(result.reason, "idle_timeout")
        self.assertTrue(result.recovered_to_wake)
        self.assertTrue(lease.is_open)
        self.assertEqual(detector.reset_calls, 1)
        events = coordinator.report()["events"]
        types = [event["type"] for event in events]
        for before, after in (
            ("wake_confirmed", "wake_microphone_closed"),
            ("wake_microphone_closed", "handoff_queued"),
            ("handoff_queued", "host_session_configured"),
            ("host_session_configured", "ack_started"),
            ("ack_started", "ack_completed"),
            ("ack_completed", "host_connected"),
        ):
            self.assertLess(types.index(before), types.index(after))
        markers = {event["type"]: event["at_ms"] for event in events}
        self.assertEqual(markers["ack_completed"] - markers["ack_started"], 350)
        ack_started = next(event for event in events if event["type"] == "ack_started")
        self.assertEqual(ack_started["ack_asset_duration_ms"], 200)

    def test_max_duration_wins_despite_continuing_activity(self):
        clock, _lease, coordinator, detector = build_runtime()

        def sleep(seconds: float) -> None:
            clock.advance(max(seconds, 0.6))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_READY:
                coordinator.host_event("connected", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_ACTIVE:
                coordinator.host_event("speech_started", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id)

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=lambda: None,
            idle_timeout_seconds=10.0,
            max_duration_seconds=1.0,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertEqual(result.reason, "max_duration")
        self.assertTrue(result.recovered_to_wake)

    def test_realtime_error_uses_same_stop_then_reopen_path(self):
        clock, lease, coordinator, detector = build_runtime()

        def sleep(seconds: float) -> None:
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_READY:
                coordinator.host_event("connected", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_ACTIVE:
                coordinator.host_event("error", coordinator.session_id, reason="network")
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id, reason="error_cleanup")

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=lambda: None,
            idle_timeout_seconds=10.0,
            max_duration_seconds=30.0,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertTrue(result.recovered_to_wake)
        self.assertTrue(lease.is_open)

    def test_acknowledgement_failure_stops_configured_host_before_reopening(self):
        clock, lease, coordinator, detector = build_runtime()

        def fail_ack() -> None:
            raise RuntimeError("playback failed")

        def sleep(seconds: float) -> None:
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id)

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=fail_ack,
            idle_timeout_seconds=1.0,
            max_duration_seconds=2.0,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertEqual(result.reason, "error:RuntimeError")
        self.assertTrue(result.recovered_to_wake)
        self.assertTrue(lease.is_open)
        self.assertFalse(coordinator.report()["active_session"])

    def test_input_ready_timeout_stops_gated_host_after_acknowledgement(self):
        clock, lease, coordinator, detector = build_runtime()
        acknowledgements: list[str] = []

        def sleep(seconds: float) -> None:
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id)

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=lambda: acknowledgements.append("played"),
            idle_timeout_seconds=1.0,
            max_duration_seconds=2.0,
            connect_timeout_seconds=0.3,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertEqual(acknowledgements, ["played"])
        self.assertEqual(result.reason, "input_ready_timeout")
        self.assertTrue(result.recovered_to_wake)
        self.assertTrue(lease.is_open)

    def test_ctrl_c_active_session_requests_stop_before_reopening(self):
        clock, lease, coordinator, detector = build_runtime()
        interrupted = False

        def sleep(seconds: float) -> None:
            nonlocal interrupted
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_READY:
                coordinator.host_event("connected", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_ACTIVE and not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id, reason="shutdown")

        controller = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=lambda: None,
            idle_timeout_seconds=10.0,
            max_duration_seconds=30.0,
            clock=clock,
            sleep=sleep,
        )
        with self.assertRaises(KeyboardInterrupt):
            controller.run_once()
        self.assertEqual(coordinator.state, HandoffState.WAKE_OWNED)
        self.assertTrue(lease.is_open)
        stop_events = [event for event in coordinator.report()["events"] if event.get("command") == "stop"]
        self.assertEqual(stop_events[-1]["reason"], "shutdown")

    def test_farewell_timeout_uses_existing_stop_and_wake_recovery(self):
        clock, lease, coordinator, detector = build_runtime()
        farewell_requested = False

        def sleep(seconds: float) -> None:
            nonlocal farewell_requested
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_READY:
                coordinator.host_event("connected", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_ACTIVE and not farewell_requested:
                farewell_requested = True
                coordinator.host_event(
                    "tool_call",
                    coordinator.session_id,
                    call_id="end-call",
                    name="end_conversation",
                    arguments="{}",
                )
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id)

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=lambda: None,
            idle_timeout_seconds=60.0,
            max_duration_seconds=600.0,
            farewell_timeout_seconds=0.3,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertTrue(farewell_requested)
        self.assertEqual(result.reason, "farewell_timeout")
        self.assertTrue(result.recovered_to_wake)
        self.assertTrue(lease.is_open)

    def test_realtime_acknowledgement_gates_input_without_local_playback(self):
        clock, lease, coordinator, detector = build_runtime()
        coordinator.request_realtime_acknowledgement_experiment()
        local_acknowledgements: list[str] = []
        acknowledgement_finished = False

        def sleep(seconds: float) -> None:
            nonlocal acknowledgement_finished
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_READY and not acknowledgement_finished:
                coordinator.host_event("realtime_ack_response_created", coordinator.session_id)
                coordinator.host_event("realtime_ack_playback_started", coordinator.session_id)
                coordinator.host_event(
                    "realtime_ack_response_done", coordinator.session_id, reason="completed"
                )
                coordinator.host_event("realtime_ack_playback_stopped", coordinator.session_id)
                acknowledgement_finished = True
            elif coordinator.state == HandoffState.HOST_READY:
                coordinator.host_event("connected", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_ACTIVE:
                coordinator.request_stop("test")
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id)

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=lambda: local_acknowledgements.append("played"),
            acknowledgement_duration_ms=480,
            idle_timeout_seconds=1.0,
            max_duration_seconds=10.0,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertEqual(local_acknowledgements, [])
        self.assertTrue(acknowledgement_finished)
        self.assertTrue(result.recovered_to_wake)

    def test_realtime_acknowledgement_timeout_uses_bounded_cleanup(self):
        clock, lease, coordinator, detector = build_runtime()
        coordinator.request_realtime_acknowledgement_experiment()

        def sleep(seconds: float) -> None:
            clock.advance(max(seconds, 0.1))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id)

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=lambda: self.fail("local ACK must remain disabled"),
            idle_timeout_seconds=1.0,
            max_duration_seconds=10.0,
            connect_timeout_seconds=0.3,
            clock=clock,
            sleep=sleep,
        ).run_once()
        self.assertEqual(result.reason, "realtime_acknowledgement_timeout")
        self.assertTrue(result.recovered_to_wake)
        self.assertTrue(lease.is_open)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import struct
import unittest

from src.realtime.controller import RealtimeSessionController
from src.realtime_host.coordinator import HandoffCoordinator, HandoffState


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class Lease:
    def __init__(self, chunks: list[bytes]) -> None:
        self.is_open = False
        self.last_overflowed = False
        self.chunks = list(chunks)

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def read_chunk(self) -> bytes:
        if not self.is_open:
            raise RuntimeError("read while closed")
        return self.chunks.pop(0)


class Detector:
    def __init__(self) -> None:
        self.detect_calls: list[bytes] = []
        self.reset_calls = 0

    def detect(self, chunk: bytes) -> bool:
        self.detect_calls.append(chunk)
        return chunk == b"wake"

    def reset(self) -> None:
        self.reset_calls += 1


def activate(coordinator: HandoffCoordinator) -> tuple[str, int]:
    coordinator.host_event("armed")
    session_id = coordinator.begin_handoff()
    cursor = coordinator.command_after(0)["command_id"]
    coordinator.host_event("transport_connected", session_id)
    coordinator.host_event("session_created", session_id)
    coordinator.host_event("session_configured", session_id)
    coordinator.enable_host_input()
    command = coordinator.command_after(cursor)
    cursor = command["command_id"]
    coordinator.host_event("connected", session_id)
    return session_id, cursor


class SessionExpiryRuntimeTests(unittest.TestCase):
    def test_ten_and_twenty_minute_sessions_request_one_relative_warning(self):
        for maximum in (600.0, 1200.0):
            with self.subTest(maximum=maximum):
                clock = Clock()
                coordinator = HandoffCoordinator(
                    Lease([]), clock=clock, session_ids=lambda: f"session-{int(maximum)}"
                )
                session_id, cursor = activate(coordinator)
                clock.advance(maximum - 30.01)
                self.assertFalse(
                    coordinator.maybe_request_session_expiry_warning(
                        max_duration_seconds=maximum
                    )
                )
                clock.advance(0.01)
                self.assertTrue(
                    coordinator.maybe_request_session_expiry_warning(
                        max_duration_seconds=maximum
                    )
                )
                command = coordinator.command_after(cursor)
                self.assertEqual(command["type"], "session_expiry_warning")
                self.assertEqual(command["session_id"], session_id)
                self.assertFalse(
                    coordinator.maybe_request_session_expiry_warning(
                        max_duration_seconds=maximum
                    )
                )

    def test_warning_waits_for_speech_response_and_playback_safe_boundary(self):
        clock = Clock()
        coordinator = HandoffCoordinator(Lease([]), clock=clock)
        session_id, _ = activate(coordinator)
        clock.advance(570.0)
        coordinator.host_event("speech_started", session_id)
        self.assertFalse(coordinator.maybe_request_session_expiry_warning(max_duration_seconds=600.0))
        coordinator.host_event("speech_stopped", session_id)
        self.assertFalse(coordinator.maybe_request_session_expiry_warning(max_duration_seconds=600.0))
        coordinator.host_event("response_created", session_id)
        coordinator.host_event("playback_started", session_id)
        coordinator.host_event("response_done", session_id, reason="completed")
        self.assertFalse(coordinator.maybe_request_session_expiry_warning(max_duration_seconds=600.0))
        coordinator.host_event("playback_stopped", session_id)
        self.assertTrue(coordinator.maybe_request_session_expiry_warning(max_duration_seconds=600.0))

    def test_maximum_recovery_gates_positive_residue_until_ready_and_quiet(self):
        clock = Clock()
        zero_chunk = struct.pack("<1600h", *([0] * 1600))  # 100 ms at 16 kHz.
        chunks = [b"wake", b"wake", b"wake"] + [b"wake"] + [zero_chunk] * 16
        lease = Lease(chunks)
        detector = Detector()
        coordinator = HandoffCoordinator(
            lease, clock=clock, session_ids=lambda: "session-expiry"
        )
        coordinator.host_event("armed")
        warning_started = False
        ready_states: list[tuple[HandoffState, str]] = []

        def play_ready() -> None:
            ready_states.append((coordinator.state, coordinator.availability()))
            clock.advance(0.555)

        def sleep(seconds: float) -> None:
            nonlocal warning_started
            clock.advance(max(seconds, 5.0))
            if coordinator.state == HandoffState.HOST_STARTING:
                coordinator.host_event("transport_connected", coordinator.session_id)
                coordinator.host_event("session_created", coordinator.session_id)
                coordinator.host_event("session_configured", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_READY:
                coordinator.host_event("connected", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_ACTIVE:
                command = coordinator.command_after(2)
                if command and command["type"] == "session_expiry_warning" and not warning_started:
                    warning_started = True
                    coordinator.host_event("session_expiry_warning_started", coordinator.session_id)
                    coordinator.host_event("session_expiry_warning_stopped", coordinator.session_id)
            elif coordinator.state == HandoffState.HOST_STOPPING:
                coordinator.host_event("stopped", coordinator.session_id)

        result = RealtimeSessionController(
            coordinator=coordinator,
            wake_detector=detector,
            play_acknowledgement=lambda: None,
            play_ready_tone=play_ready,
            idle_timeout_seconds=100.0,
            max_duration_seconds=40.0,
            session_expiry_warning_enabled=True,
            session_expiry_warning_lead_seconds=30.0,
            wake_recovery_cooldown_seconds=1.0,
            wake_recovery_quiet_seconds=0.5,
            wake_recovery_max_seconds=6.0,
            clock=clock,
            sleep=sleep,
        ).run_once()

        self.assertEqual(result.reason, "max_duration")
        self.assertTrue(result.recovered_to_wake)
        self.assertEqual(ready_states, [(HandoffState.WAKE_RECOVERING, "busy")])
        self.assertEqual(detector.detect_calls, [b"wake", b"wake"])
        self.assertEqual(detector.reset_calls, 1)
        self.assertEqual(coordinator.availability(), "wake_listening")
        event_types = [event["type"] for event in coordinator.report()["events"]]
        for event in (
            "session_expiry_warning_armed",
            "host_session_expiry_warning_started",
            "host_session_expiry_warning_stopped",
            "wake_microphone_acquired",
            "wake_ready_cue_started",
            "wake_recovery_residue_discarded",
            "wake_detector_reset",
            "wake_recovery_quiet_succeeded",
            "wake_microphone_reopened",
        ):
            self.assertIn(event, event_types)
        self.assertLess(
            event_types.index("wake_recovery_quiet_succeeded"),
            event_types.index("wake_microphone_reopened"),
        )


if __name__ == "__main__":
    unittest.main()

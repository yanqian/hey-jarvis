"""Wake-to-WebRTC lifecycle controller with no PCM bridge transport."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Protocol

from src.realtime_host.coordinator import HandoffCoordinator, HandoffState


class WakeDetector(Protocol):
    def detect(self, pcm_chunk: bytes) -> bool: ...


@dataclass(frozen=True)
class RealtimeSessionResult:
    session_id: str | None
    reason: str
    recovered_to_wake: bool


class RealtimeSessionController:
    """Run one local wake followed by one continuous Realtime session."""

    def __init__(
        self,
        *,
        coordinator: HandoffCoordinator,
        wake_detector: WakeDetector,
        play_acknowledgement: Callable[[], None],
        acknowledgement_duration_ms: int | None = None,
        idle_timeout_seconds: float,
        max_duration_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        poll_seconds: float = 0.05,
        connect_timeout_seconds: float = 20.0,
        close_timeout_seconds: float = 5.0,
        farewell_timeout_seconds: float = 8.0,
        wake_confirmation_frames: int = 2,
    ) -> None:
        self.coordinator = coordinator
        self.wake_detector = wake_detector
        self.play_acknowledgement = play_acknowledgement
        if acknowledgement_duration_ms is not None and not 1 <= acknowledgement_duration_ms <= 60_000:
            raise ValueError("acknowledgement_duration_ms must be between 1 and 60000")
        self.acknowledgement_duration_ms = acknowledgement_duration_ms
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_duration_seconds = max_duration_seconds
        self.clock = clock
        self.sleep = sleep
        self.poll_seconds = poll_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self.close_timeout_seconds = close_timeout_seconds
        if farewell_timeout_seconds <= 0:
            raise ValueError("farewell_timeout_seconds must be greater than zero")
        self.farewell_timeout_seconds = farewell_timeout_seconds
        self.wake_confirmation_frames = max(1, wake_confirmation_frames)

    def run_once(self) -> RealtimeSessionResult:
        session_id: str | None = None
        try:
            self._wait_for_armed_host()
            self._wait_for_local_wake()
            self.coordinator.record_local_timing_marker("wake_confirmed")
            self.coordinator.release_wake_for_acknowledgement()
            session_id = self.coordinator.begin_handoff()
            if not self._wait_until_not(HandoffState.HOST_STARTING, self.connect_timeout_seconds):
                self.coordinator.request_stop("connect_timeout")
            if self.coordinator.state == HandoffState.HOST_READY:
                if self.coordinator.active_acknowledgement_mode == "local":
                    self.coordinator.record_local_timing_marker(
                        "ack_started",
                        ack_asset_duration_ms=self.acknowledgement_duration_ms,
                    )
                    self.play_acknowledgement()
                    self.coordinator.record_local_timing_marker("ack_completed")
                elif self.coordinator.active_acknowledgement_mode == "cached":
                    if not self._wait_for_cached_acknowledgement(self.connect_timeout_seconds):
                        self.coordinator.request_stop("cached_acknowledgement_timeout")
                elif not self._wait_for_realtime_acknowledgement(
                    self.connect_timeout_seconds
                ):
                    self.coordinator.request_stop("realtime_acknowledgement_timeout")
                if self.coordinator.state == HandoffState.HOST_READY:
                    self.coordinator.enable_host_input()
                if not self._wait_until_not(
                    HandoffState.HOST_READY,
                    self.connect_timeout_seconds,
                ):
                    self.coordinator.request_stop("input_ready_timeout")
            while self.coordinator.state in {
                HandoffState.HOST_ACTIVE,
                HandoffState.HOST_FAREWELL,
            }:
                reason = self.coordinator.timeout_reason(
                    idle_seconds=self.idle_timeout_seconds,
                    max_duration_seconds=self.max_duration_seconds,
                    farewell_seconds=self.farewell_timeout_seconds,
                )
                if reason is not None:
                    self.coordinator.request_stop(reason)
                    break
                self.sleep(self.poll_seconds)
            recovered = self._wait_for_wake_ownership()
            if recovered:
                reset = getattr(self.wake_detector, "reset", None)
                if reset is not None:
                    reset()
            return RealtimeSessionResult(
                session_id,
                self._final_reason("closed" if recovered else "close_timeout"),
                recovered,
            )
        except KeyboardInterrupt:
            self.coordinator.request_stop("shutdown")
            self._wait_for_wake_ownership()
            raise
        except Exception as exc:
            self.coordinator.request_stop("controller_error")
            if session_id is None:
                self.coordinator.restore_wake_microphone("pre_session_error")
            recovered = self._wait_for_wake_ownership()
            if recovered:
                reset = getattr(self.wake_detector, "reset", None)
                if reset is not None:
                    reset()
            return RealtimeSessionResult(session_id, f"error:{type(exc).__name__}", recovered)

    def _wait_for_armed_host(self) -> None:
        while not self.coordinator.armed:
            self.sleep(self.poll_seconds)

    def _wait_for_local_wake(self) -> None:
        consecutive_detections = 0
        while True:
            pcm_chunk = self.coordinator.read_wake_chunk()
            if self.wake_detector.detect(pcm_chunk):
                consecutive_detections += 1
                if consecutive_detections >= self.wake_confirmation_frames:
                    return
            else:
                consecutive_detections = 0

    def _wait_until_not(self, state: HandoffState, timeout: float) -> bool:
        deadline = self.clock() + timeout
        while self.coordinator.state == state and self.clock() < deadline:
            self.sleep(self.poll_seconds)
        return self.coordinator.state != state

    def _wait_for_realtime_acknowledgement(self, timeout: float) -> bool:
        deadline = self.clock() + timeout
        while self.coordinator.state == HandoffState.HOST_READY and self.clock() < deadline:
            if self.coordinator.realtime_acknowledgement_complete:
                return True
            self.sleep(self.poll_seconds)
        return self.coordinator.realtime_acknowledgement_complete

    def _wait_for_cached_acknowledgement(self, timeout: float) -> bool:
        deadline = self.clock() + timeout
        while self.coordinator.state == HandoffState.HOST_READY and self.clock() < deadline:
            if self.coordinator.cached_acknowledgement_complete:
                return True
            self.sleep(self.poll_seconds)
        return self.coordinator.cached_acknowledgement_complete

    def _wait_for_wake_ownership(self) -> bool:
        if self.coordinator.state == HandoffState.WAKE_OWNED:
            return self.coordinator.wake_microphone_open
        deadline = self.clock() + self.close_timeout_seconds
        while self.coordinator.state != HandoffState.WAKE_OWNED and self.clock() < deadline:
            self.sleep(self.poll_seconds)
        return self.coordinator.state == HandoffState.WAKE_OWNED and self.coordinator.wake_microphone_open

    def _final_reason(self, fallback: str) -> str:
        events = self.coordinator.report()["events"]
        for event in reversed(events):
            if event.get("type") == "host_command" and event.get("command") == "stop":
                return str(event.get("reason", fallback))
        return fallback

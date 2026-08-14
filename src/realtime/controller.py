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
        wake_threshold: float | None = None,
        wake_diagnostics: object | None = None,
        shutdown_requested: Callable[[], bool] = lambda: False,
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
        if wake_threshold is not None and not 0.0 <= wake_threshold <= 1.0:
            raise ValueError("wake_threshold must be between 0 and 1")
        self.wake_threshold = wake_threshold
        self.wake_diagnostics = wake_diagnostics
        self.shutdown_requested = shutdown_requested

    def run_once(self) -> RealtimeSessionResult:
        session_id: str | None = None
        try:
            self._raise_if_shutting_down()
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
            if self.shutdown_requested():
                return RealtimeSessionResult(session_id, "shutdown", False)
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
            self._raise_if_shutting_down()
            self.sleep(self.poll_seconds)
        self._raise_if_shutting_down()

    def _wait_for_local_wake(self) -> None:
        consecutive_detections = 0
        while True:
            self._raise_if_shutting_down()
            pcm_chunk = self.coordinator.read_wake_chunk()
            self._raise_if_shutting_down()
            score_method = getattr(self.wake_detector, "score", None)
            if self.wake_diagnostics is not None and self.wake_threshold is not None and score_method is not None:
                score = float(score_method(pcm_chunk))
                detected = score >= self.wake_threshold
            else:
                detected = self.wake_detector.detect(pcm_chunk)
                score = 1.0 if detected else 0.0
            overflowed = self.coordinator.wake_microphone_overflowed
            if overflowed and detected:
                self._record_wake_diagnostic(
                    pcm_chunk, "overflow", score, consecutive_detections, overflowed
                )
            if detected:
                consecutive_detections += 1
                if consecutive_detections >= self.wake_confirmation_frames:
                    self._record_wake_diagnostic(
                        pcm_chunk, "confirmed", score, consecutive_detections, overflowed
                    )
                    return
                self._record_wake_diagnostic(
                    pcm_chunk, "positive", score, consecutive_detections, overflowed
                )
            else:
                event = "reset" if consecutive_detections else (
                    "overflow" if overflowed else "near_threshold"
                )
                if consecutive_detections or overflowed or (
                    self.wake_threshold is not None
                    and score >= max(0.05, self.wake_threshold - 0.25)
                ):
                    self._record_wake_diagnostic(
                        pcm_chunk, event, score, consecutive_detections, overflowed
                    )
                consecutive_detections = 0

    def _record_wake_diagnostic(
        self,
        pcm_chunk: bytes,
        event: str,
        score: float,
        consecutive: int,
        overflowed: bool,
    ) -> None:
        observe = getattr(self.wake_diagnostics, "observe", None)
        if observe is None or self.wake_threshold is None:
            return
        try:
            observe(
                pcm_chunk,
                event=event,
                score=score,
                threshold=self.wake_threshold,
                consecutive=min(consecutive, self.wake_confirmation_frames),
                required=self.wake_confirmation_frames,
                overflowed=overflowed,
            )
        except Exception:
            return

    def _wait_until_not(self, state: HandoffState, timeout: float) -> bool:
        deadline = self.clock() + timeout
        while self.coordinator.state == state and self.clock() < deadline:
            self._raise_if_shutting_down()
            self.sleep(self.poll_seconds)
        self._raise_if_shutting_down()
        return self.coordinator.state != state

    def _wait_for_realtime_acknowledgement(self, timeout: float) -> bool:
        deadline = self.clock() + timeout
        while self.coordinator.state == HandoffState.HOST_READY and self.clock() < deadline:
            self._raise_if_shutting_down()
            if self.coordinator.realtime_acknowledgement_complete:
                return True
            self.sleep(self.poll_seconds)
        return self.coordinator.realtime_acknowledgement_complete

    def _wait_for_cached_acknowledgement(self, timeout: float) -> bool:
        deadline = self.clock() + timeout
        while self.coordinator.state == HandoffState.HOST_READY and self.clock() < deadline:
            self._raise_if_shutting_down()
            if self.coordinator.cached_acknowledgement_complete:
                return True
            self.sleep(self.poll_seconds)
        return self.coordinator.cached_acknowledgement_complete

    def _wait_for_wake_ownership(self) -> bool:
        if self.shutdown_requested():
            return False
        if self.coordinator.state == HandoffState.WAKE_OWNED:
            return self.coordinator.wake_microphone_open
        deadline = self.clock() + self.close_timeout_seconds
        while self.coordinator.state != HandoffState.WAKE_OWNED and self.clock() < deadline:
            if self.shutdown_requested():
                return False
            self.sleep(self.poll_seconds)
        return self.coordinator.state == HandoffState.WAKE_OWNED and self.coordinator.wake_microphone_open

    def _final_reason(self, fallback: str) -> str:
        events = self.coordinator.report()["events"]
        for event in reversed(events):
            if event.get("type") == "host_command" and event.get("command") == "stop":
                return str(event.get("reason", fallback))
        return fallback

    def _raise_if_shutting_down(self) -> None:
        if self.shutdown_requested():
            raise _ControllerShutdown


class _ControllerShutdown(Exception):
    """Internal control-flow signal that must not trigger microphone recovery."""

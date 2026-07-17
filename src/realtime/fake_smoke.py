"""Dependency-free smoke for one wake-to-Realtime-to-wake cycle."""

from __future__ import annotations

from src.realtime.controller import RealtimeSessionController
from src.realtime_host.coordinator import HandoffCoordinator, HandoffState


class _Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _Lease:
    def __init__(self) -> None:
        self.is_open = False
        self._chunks = [b"quiet", b"wake", b"wake"]

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def read_chunk(self) -> bytes:
        return self._chunks.pop(0)


class _Detector:
    def detect(self, chunk: bytes) -> bool:
        return chunk == b"wake"

    def reset(self) -> None:
        pass


def main() -> int:
    clock = _Clock()
    coordinator = HandoffCoordinator(_Lease(), clock=clock, session_ids=lambda: "fake-session")
    coordinator.host_event("armed")
    turns = 0

    def sleep(seconds: float) -> None:
        nonlocal turns
        clock.advance(max(seconds, 0.1))
        if coordinator.state == HandoffState.HOST_STARTING:
            coordinator.host_event("transport_connected", coordinator.session_id)
            coordinator.host_event("session_created", coordinator.session_id)
            coordinator.host_event("connected", coordinator.session_id)
        elif coordinator.state == HandoffState.HOST_ACTIVE:
            turns += 1
            coordinator.host_event("speech_started", coordinator.session_id)
            coordinator.host_event("speech_stopped", coordinator.session_id)
            coordinator.host_event("response_created", coordinator.session_id)
            coordinator.host_event("response_done", coordinator.session_id, reason="completed")
            if turns >= 2:
                clock.advance(2.0)
        elif coordinator.state == HandoffState.HOST_STOPPING:
            coordinator.host_event("stopped", coordinator.session_id, reason="fake_close")

    result = RealtimeSessionController(
        coordinator=coordinator,
        wake_detector=_Detector(),
        play_acknowledgement=lambda: None,
        idle_timeout_seconds=1.0,
        max_duration_seconds=30.0,
        clock=clock,
        sleep=sleep,
    ).run_once()
    print(
        "Realtime fake smoke: "
        f"turns={turns} reason={result.reason} recovered_to_wake={str(result.recovered_to_wake).lower()}"
    )
    return 0 if turns >= 2 and result.recovered_to_wake else 1


if __name__ == "__main__":
    raise SystemExit(main())

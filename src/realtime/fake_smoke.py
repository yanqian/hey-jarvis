"""Dependency-free smoke for the complete Realtime MVP lifecycle."""

from __future__ import annotations

import json
from dataclasses import dataclass

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
        self.calls: list[str] = []

    def open(self) -> None:
        self.is_open = True
        self.calls.append("open")

    def close(self) -> None:
        self.is_open = False
        self.calls.append("close")

    def read_chunk(self) -> bytes:
        return self._chunks.pop(0)


class _Detector:
    def detect(self, chunk: bytes) -> bool:
        return chunk == b"wake"

    def reset(self) -> None:
        pass


@dataclass(frozen=True)
class FakeSmokeResult:
    wake: bool
    exclusive_handoff: bool
    connected: bool
    user_turns: int
    assistant_completions: int
    barge_in: bool
    calculator_output: bool
    end_phrase: bool
    closed: bool
    recovered_to_wake: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.wake,
                self.exclusive_handoff,
                self.connected,
                self.user_turns == 2,
                self.assistant_completions == 2,
                self.barge_in,
                self.calculator_output,
                self.end_phrase,
                self.closed,
                self.recovered_to_wake,
            )
        )


def run_fake_smoke() -> FakeSmokeResult:
    """Exercise the full MVP without hardware, network, credentials, or real sleeps."""

    clock = _Clock()
    lease = _Lease()
    coordinator = HandoffCoordinator(
        lease,
        clock=clock,
        session_ids=lambda: "fake-session",
        end_phrases=("goodbye",),
    )
    coordinator.host_event("armed")
    stage = 0
    user_turns = 0
    assistant_completions = 0
    connected = False
    exclusive_handoff = False
    barge_in = False
    calculator_output = False

    def sleep(seconds: float) -> None:
        nonlocal stage, user_turns, assistant_completions
        nonlocal connected, exclusive_handoff, barge_in, calculator_output
        clock.advance(max(seconds, 0.1))
        session_id = coordinator.session_id
        if coordinator.state == HandoffState.HOST_STARTING:
            exclusive_handoff = not lease.is_open
            coordinator.host_event("microphone_requested", session_id)
            coordinator.host_event("microphone_acquired", session_id, echoCancellation=True)
            coordinator.host_event("transport_connected", session_id)
            coordinator.host_event("session_created", session_id)
            coordinator.host_event("connected", session_id)
            connected = coordinator.state == HandoffState.HOST_ACTIVE
        elif coordinator.state == HandoffState.HOST_ACTIVE and stage == 0:
            user_turns += 1
            coordinator.host_event("speech_started", session_id)
            coordinator.host_event("speech_stopped", session_id)
            coordinator.host_event("response_created", session_id)
            coordinator.host_event("response_done", session_id, reason="completed")
            assistant_completions += 1
            stage = 1
        elif coordinator.state == HandoffState.HOST_ACTIVE and stage == 1:
            user_turns += 1
            coordinator.host_event("speech_started", session_id)
            coordinator.host_event("speech_stopped", session_id)
            coordinator.host_event("response_created", session_id)
            # A new user utterance while the assistant response is active is the
            # server-managed interruption contract; no client truncation is sent.
            coordinator.host_event("speech_started", session_id)
            coordinator.host_event("response_done", session_id, reason="cancelled")
            barge_in = True
            coordinator.host_event(
                "tool_call",
                session_id,
                call_id="fake-call",
                name="calculator",
                arguments=json.dumps({"expression": "100 * 1000"}),
            )
            command = coordinator.command_after(1)
            calculator_output = bool(
                command
                and command["type"] == "tool_result"
                and json.loads(str(command["output"]))["answer"] == "The answer is 100000."
            )
            coordinator.host_event("response_created", session_id)
            coordinator.host_event("response_done", session_id, reason="completed")
            assistant_completions += 1
            stage = 2
        elif coordinator.state == HandoffState.HOST_ACTIVE and stage == 2:
            coordinator.host_event(
                "tool_call",
                session_id,
                call_id="fake-end-call",
                name="end_conversation",
                arguments="{}",
            )
            stage = 3
        elif coordinator.state == HandoffState.HOST_STOPPING:
            coordinator.host_event("stopped", session_id, reason="fake_close")

    result = RealtimeSessionController(
        coordinator=coordinator,
        wake_detector=_Detector(),
        play_acknowledgement=lambda: None,
        idle_timeout_seconds=30.0,
        max_duration_seconds=60.0,
        clock=clock,
        sleep=sleep,
    ).run_once()
    event_types = [event["type"] for event in coordinator.report()["events"]]
    return FakeSmokeResult(
        wake="wake_microphone_closed" in event_types,
        exclusive_handoff=exclusive_handoff,
        connected=connected,
        user_turns=user_turns,
        assistant_completions=assistant_completions,
        barge_in=barge_in,
        calculator_output=calculator_output,
        end_phrase="host_end_conversation_tool" in event_types,
        closed=stage == 3,
        recovered_to_wake=result.recovered_to_wake and lease.is_open,
    )


def main() -> int:
    result = run_fake_smoke()
    fields = " ".join(f"{key}={str(value).lower()}" for key, value in result.__dict__.items())
    print(f"Realtime fake smoke: {fields}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

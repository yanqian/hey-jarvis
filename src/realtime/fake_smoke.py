"""Dependency-free smoke for the complete Realtime MVP lifecycle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.realtime.controller import RealtimeSessionController
from src.realtime_host.coordinator import HandoffCoordinator, HandoffState
from src.tools import ProviderConfig


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


class _ToolClient:
    def __init__(self) -> None:
        self.responses = [
            {
                "results": [
                    {
                        "name": "Singapore",
                        "country": "Singapore",
                        "latitude": 1.29,
                        "longitude": 103.85,
                        "timezone": "Asia/Singapore",
                    }
                ]
            },
            {
                "current": {
                    "time": "2026-07-28T15:00",
                    "temperature_2m": 30.0,
                    "apparent_temperature": 34.0,
                    "weather_code": 3,
                    "precipitation": 0.0,
                    "rain": 0.0,
                }
            },
            {
                "date": "2026-07-28",
                "base": "USD",
                "quote": "SGD",
                "rate": 1.35,
            },
            {
                "c": 193.12,
                "d": 1.23,
                "dp": 0.64,
                "h": 194.0,
                "l": 190.0,
                "o": 191.0,
                "pc": 191.89,
                "t": 1783306800,
            },
        ]

    def get_json(self, _url: str, *, params=None, timeout_seconds: float):
        return self.responses.pop(0)


@dataclass(frozen=True)
class FakeSmokeResult:
    wake: bool
    exclusive_handoff: bool
    connected: bool
    user_turns: int
    assistant_completions: int
    barge_in: bool
    calculator_output: bool
    weather_output: bool
    local_time_output: bool
    fx_output: bool
    stock_output: bool
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
                self.weather_output,
                self.local_time_output,
                self.fx_output,
                self.stock_output,
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
        acknowledgement_mode="realtime",
        end_phrases=("goodbye",),
        tool_provider_config=ProviderConfig(
            default_location="Singapore",
            finnhub_api_key="fake-finnhub-key",
        ),
        tool_http_client=_ToolClient(),
        tool_now_provider=lambda: datetime(
            2026,
            7,
            28,
            16,
            42,
            tzinfo=timezone(timedelta(hours=8), name="+08"),
        ),
    )
    coordinator.host_event("armed")
    stage = 0
    user_turns = 0
    assistant_completions = 0
    connected = False
    acknowledgement_completed = False
    exclusive_handoff = False
    barge_in = False
    calculator_output = False
    weather_output = False
    local_time_output = False
    fx_output = False
    stock_output = False

    def sleep(seconds: float) -> None:
        nonlocal stage, user_turns, assistant_completions
        nonlocal connected, acknowledgement_completed, exclusive_handoff, barge_in
        nonlocal calculator_output, weather_output, local_time_output, fx_output
        nonlocal stock_output
        clock.advance(max(seconds, 0.1))
        session_id = coordinator.session_id
        if coordinator.state == HandoffState.HOST_STARTING:
            exclusive_handoff = not lease.is_open
            coordinator.host_event("microphone_requested", session_id)
            coordinator.host_event("microphone_acquired", session_id, echoCancellation=True)
            coordinator.host_event("transport_connected", session_id)
            coordinator.host_event("session_created", session_id)
            coordinator.host_event("session_configured", session_id)
        elif coordinator.state == HandoffState.HOST_READY:
            if not acknowledgement_completed:
                coordinator.host_event("realtime_ack_response_created", session_id)
                coordinator.host_event("realtime_ack_playback_started", session_id)
                coordinator.host_event(
                    "realtime_ack_response_done", session_id, reason="completed"
                )
                coordinator.host_event("realtime_ack_playback_stopped", session_id)
                acknowledgement_completed = True
            else:
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
            command = coordinator.command_after(2)
            calculator_output = bool(
                command
                and command["type"] == "tool_result"
                and json.loads(str(command["output"]))["answer"] == "The answer is 100000."
            )
            coordinator.host_event(
                "tool_call",
                session_id,
                call_id="fake-weather-call",
                name="weather",
                arguments=json.dumps({"intent": "current"}),
            )
            weather_command = coordinator.command_after(int(command["command_id"]))
            weather_payload = (
                json.loads(str(weather_command["output"])) if weather_command else {}
            )
            weather_output = bool(
                weather_command
                and weather_command["type"] == "tool_result"
                and weather_payload["status"] == "success"
                and weather_payload["data"]["location"].startswith("Singapore")
            )
            coordinator.host_event(
                "tool_call",
                session_id,
                call_id="fake-local-time-call",
                name="local_time",
                arguments="{}",
            )
            time_command = coordinator.command_after(
                int(weather_command["command_id"])
            )
            time_payload = (
                json.loads(str(time_command["output"])) if time_command else {}
            )
            local_time_output = bool(
                time_command
                and time_command["type"] == "tool_result"
                and time_payload["status"] == "success"
                and time_payload["data"]["time"] == "16:42"
                and time_payload["data"]["timezone"] == "+08"
            )
            coordinator.host_event(
                "tool_call",
                session_id,
                call_id="fake-fx-call",
                name="fx",
                arguments=json.dumps(
                    {"amount": 100, "base": "USD", "quote": "SGD"}
                ),
            )
            fx_command = coordinator.command_after(int(time_command["command_id"]))
            fx_payload = json.loads(str(fx_command["output"])) if fx_command else {}
            fx_output = bool(
                fx_command
                and fx_command["type"] == "tool_result"
                and fx_payload["status"] == "success"
                and fx_payload["data"]["base"] == "USD"
                and fx_payload["data"]["quote"] == "SGD"
                and fx_payload["data"]["converted_amount"] == 135.0
            )
            coordinator.host_event(
                "tool_call",
                session_id,
                call_id="fake-stock-call",
                name="stock",
                arguments=json.dumps({"symbol": "AAPL"}),
            )
            stock_command = coordinator.command_after(int(fx_command["command_id"]))
            stock_payload = (
                json.loads(str(stock_command["output"])) if stock_command else {}
            )
            stock_output = bool(
                stock_command
                and stock_command["type"] == "tool_result"
                and stock_payload["status"] == "success"
                and stock_payload["data"]["symbol"] == "AAPL"
                and stock_payload["data"]["current_price"] == 193.12
                and "not trading advice" in stock_payload["answer"]
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
        elif coordinator.state == HandoffState.HOST_FAREWELL and stage == 3:
            coordinator.host_event("farewell_started", session_id)
            coordinator.host_event("farewell_response_created", session_id)
            coordinator.host_event("farewell_playback_started", session_id)
            coordinator.host_event("farewell_response_done", session_id, reason="completed")
            coordinator.host_event("farewell_playback_stopped", session_id)
            stage = 4
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
        weather_output=weather_output,
        local_time_output=local_time_output,
        fx_output=fx_output,
        stock_output=stock_output,
        end_phrase="host_end_conversation_tool" in event_types,
        closed=stage == 4,
        recovered_to_wake=result.recovered_to_wake and lease.is_open,
    )


def main() -> int:
    result = run_fake_smoke()
    fields = " ".join(f"{key}={str(value).lower()}" for key, value in result.__dict__.items())
    print(f"Realtime fake smoke: {fields}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

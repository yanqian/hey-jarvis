from __future__ import annotations

import json
import http.client
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from src.realtime_host.coordinator import (
    MAX_TOOL_ARGUMENT_CHARS,
    HandoffCoordinator,
    HandoffError,
    HandoffState,
)
from src.realtime_host import server
from src.tools import ProviderConfig, ProviderError


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


class FakeSDPResponse(FakeResponse):
    def read(self) -> bytes:
        return str(self.payload).encode()


class FakeJsonClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, url: str, *, params=None, timeout_seconds: float):
        self.calls.append((url, dict(params or {})))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def weather_location(name: str = "Singapore") -> dict[str, object]:
    return {
        "results": [
            {
                "name": name,
                "country": "Singapore" if name == "Singapore" else "Japan",
                "latitude": 1.29 if name == "Singapore" else 35.68,
                "longitude": 103.85 if name == "Singapore" else 139.69,
                "timezone": "Asia/Singapore" if name == "Singapore" else "Asia/Tokyo",
            }
        ]
    }


def current_weather() -> dict[str, object]:
    return {
        "current": {
            "time": "2026-07-28T15:00",
            "temperature_2m": 30.0,
            "apparent_temperature": 34.0,
            "weather_code": 3,
            "precipitation": 0.0,
            "rain": 0.0,
        }
    }


def today_weather() -> dict[str, object]:
    return {
        "daily": {
            "time": ["2026-07-28", "2026-07-29"],
            "weather_code": [61, 3],
            "temperature_2m_min": [25.0, 26.0],
            "temperature_2m_max": [31.0, 32.0],
            "apparent_temperature_max": [35.0, 36.0],
            "precipitation_sum": [3.0, 0.0],
            "rain_sum": [3.0, 0.0],
            "precipitation_probability_max": [70.0, 20.0],
        }
    }


class RealtimeHostTests(unittest.TestCase):
    def build_coordinator(self):
        lease = FakeLease()
        ids = iter(f"session-{index}" for index in range(10))
        coordinator = HandoffCoordinator(lease, clock=lambda: 1.25, session_ids=lambda: next(ids))
        return coordinator, lease

    def test_product_loopback_capability_bootstraps_an_httponly_cookie(self):
        host = server.build_server(
            "127.0.0.1",
            0,
            capability_lease="session-product-1",
        )
        thread = threading.Thread(target=host.serve_forever, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", host.server_port, timeout=2)
        try:
            connection.request("GET", "/health")
            self.assertEqual(connection.getresponse().status, HTTPStatus.FORBIDDEN)

            connection.request("GET", "/?lease=wrong")
            self.assertEqual(connection.getresponse().status, HTTPStatus.FORBIDDEN)

            connection.request("GET", "/?lease=session-product-1")
            bootstrap = connection.getresponse()
            self.assertEqual(bootstrap.status, HTTPStatus.SEE_OTHER)
            cookie = bootstrap.getheader("Set-Cookie")
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=Lax", cookie)
            self.assertNotIn("SameSite=None", cookie)
            self.assertNotIn("OPENAI", cookie)

            connection.request(
                "GET",
                "/health",
                headers={"Cookie": cookie.split(";", 1)[0]},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, HTTPStatus.OK)
            self.assertEqual(json.loads(response.read()), {"status": "ok"})
        finally:
            connection.close()
            host.shutdown()
            host.server_close()
            host.coordinator.close()

    def activate_session(
        self,
        coordinator: HandoffCoordinator,
        session_id: str,
        *,
        host_id: str | None = None,
    ) -> int:
        coordinator.host_event("transport_connected", session_id, host_id=host_id)
        coordinator.host_event("session_created", session_id, host_id=host_id)
        coordinator.host_event("session_configured", session_id, host_id=host_id)
        coordinator.enable_host_input()
        cursor = 0
        enable = None
        while command := coordinator.command_after(cursor, host_id=host_id):
            cursor = int(command["command_id"])
            if command["type"] == "enable_input" and command["session_id"] == session_id:
                enable = command
                break
        self.assertIsNotNone(enable)
        self.assertEqual(enable["type"], "enable_input")
        coordinator.host_event("connected", session_id, host_id=host_id)
        return int(enable["command_id"])

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
            cursor = self.activate_session(coordinator, session_id)
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

    def test_voice_availability_tracks_actual_microphone_ownership(self):
        coordinator, lease = self.build_coordinator()
        self.assertEqual(coordinator.availability(), "ready")

        coordinator.host_event("armed")
        self.assertTrue(lease.is_open)
        self.assertEqual(coordinator.availability(), "wake_listening")

        session_id = coordinator.begin_handoff()
        self.assertFalse(lease.is_open)
        self.assertEqual(coordinator.availability(), "busy")

        coordinator.host_event("error", session_id, reason="test")
        self.assertEqual(coordinator.availability(), "busy")
        coordinator.host_event("stopped", session_id, reason="test")
        self.assertTrue(lease.is_open)
        self.assertEqual(coordinator.availability(), "wake_listening")

        lease.close()
        self.assertEqual(coordinator.availability(), "resume_required")

    def test_availability_endpoint_exposes_only_the_bounded_state(self):
        coordinator, _lease = self.build_coordinator()
        responses: list[tuple[HTTPStatus, dict[str, object]]] = []
        handler = object.__new__(server.HostRequestHandler)
        handler.path = "/api/availability"
        handler.server = SimpleNamespace(coordinator=coordinator)
        handler._json = lambda status, payload: responses.append((status, dict(payload)))

        handler.do_GET()

        self.assertEqual(
            responses,
            [(HTTPStatus.OK, {"availability": "ready"})],
        )

    def test_only_the_armed_browser_instance_can_consume_commands_or_emit_events(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
        coordinator.host_event("armed", host_id="host-current")
        session_id = coordinator.begin_handoff()
        self.assertIsNone(coordinator.command_after(0, host_id="host-stale"))
        self.assertEqual(coordinator.command_after(0, host_id="host-current")["type"], "start")
        coordinator.host_event("transport_connected", session_id, host_id="host-current")
        coordinator.host_event("session_created", session_id, host_id="host-current")
        coordinator.host_event("session_configured", session_id, host_id="host-current")
        coordinator.enable_host_input()
        with self.assertRaisesRegex(HandoffError, "armed host"):
            coordinator.host_event("connected", session_id, host_id="host-stale")
        coordinator.host_event("connected", session_id, host_id="host-current")
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_input_ready_requires_configured_session_and_one_explicit_enable(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        with self.assertRaisesRegex(HandoffError, "before enablement"):
            coordinator.host_event("connected", session_id)
        with self.assertRaisesRegex(HandoffError, "before transport"):
            coordinator.host_event("session_configured", session_id)
        coordinator.host_event("transport_connected", session_id)
        coordinator.host_event("session_created", session_id)
        coordinator.host_event("session_configured", session_id)
        self.assertEqual(coordinator.state, HandoffState.HOST_READY)
        with self.assertRaisesRegex(HandoffError, "before input readiness"):
            coordinator.host_event("speech_started", session_id)
        coordinator.enable_host_input()
        self.assertEqual(coordinator.command_after(1)["type"], "enable_input")
        with self.assertRaisesRegex(HandoffError, "already requested"):
            coordinator.enable_host_input()
        coordinator.host_event("connected", session_id)
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)
        with self.assertRaisesRegex(HandoffError, "before enablement"):
            coordinator.host_event("connected", session_id)

    def test_input_level_diagnostics_are_explicit_one_shot_and_state_bounded(self):
        coordinator, lease = self.build_coordinator()
        with self.assertRaisesRegex(HandoffError, "armed"):
            coordinator.request_input_level_diagnostics()
        coordinator.host_event("armed")
        coordinator.request_input_level_diagnostics()
        first_session = coordinator.begin_handoff()
        first_start = coordinator.command_after(0)
        self.assertIs(first_start["input_level_diagnostics"], True)
        self.assertFalse(lease.is_open)
        with self.assertRaisesRegex(HandoffError, "wake owns"):
            coordinator.request_input_level_diagnostics()
        coordinator.host_event("error", first_session, reason="test")
        stop_command = coordinator.command_after(first_start["command_id"])
        coordinator.host_event("stopped", first_session, reason="test")

        second_session = coordinator.begin_handoff()
        second_start = coordinator.command_after(stop_command["command_id"])
        self.assertEqual(second_start["session_id"], second_session)
        self.assertNotIn("input_level_diagnostics", second_start)

    def test_input_level_diagnostics_endpoint_arms_the_next_handoff(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        responses: list[tuple[HTTPStatus, dict[str, object]]] = []
        handler = object.__new__(server.HostRequestHandler)
        handler.path = "/api/input-level-diagnostics"
        handler.server = SimpleNamespace(coordinator=coordinator)
        handler._json = lambda status, payload: responses.append((status, dict(payload)))

        handler.do_POST()

        self.assertEqual(
            responses,
            [(HTTPStatus.OK, {"status": "armed_for_next_handoff"})],
        )
        coordinator.begin_handoff()
        self.assertIs(coordinator.command_after(0)["input_level_diagnostics"], True)

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
                self.activate_session(coordinator, session_id)
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
        self.activate_session(coordinator, session_id)
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
        self.activate_session(coordinator, session_id)
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
        cursor = self.activate_session(coordinator, session_id)
        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="call-1",
            name="calculator",
            arguments=json.dumps({"expression": "(2 + 3) * 4"}),
        )
        command = coordinator.command_after(cursor)
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
            ("weather", json.dumps({"expression": "2+2"}), "Weather arguments were invalid."),
            ("shell", json.dumps({"command": "pwd"}), "Unsupported Realtime tool."),
        )
        for index, (name, arguments, expected) in enumerate(cases):
            with self.subTest(name=name, arguments=arguments):
                lease = FakeLease()
                coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                cursor = self.activate_session(coordinator, session_id)
                coordinator.host_event(
                    "tool_call", session_id, call_id=f"call-{index}", name=name, arguments=arguments
                )
                output = json.loads(coordinator.command_after(cursor)["output"])
                self.assertEqual(output["status"], "error")
                self.assertIn(expected, output["answer"])
                self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_realtime_weather_defaults_to_singapore_and_preserves_explicit_location(self):
        cases = (
            (
                {"intent": "today"},
                [weather_location(), today_weather()],
                "Singapore",
                "today",
            ),
            (
                {"location": "东京", "intent": "current"},
                [weather_location("Tokyo"), current_weather()],
                "Tokyo",
                "current",
            ),
        )
        for index, (arguments, responses, expected_location, expected_intent) in enumerate(cases):
            with self.subTest(arguments=arguments):
                lease = FakeLease()
                client = FakeJsonClient(responses)
                coordinator = HandoffCoordinator(
                    lease,
                    session_ids=lambda: "session-1",
                    tool_provider_config=ProviderConfig(default_location="Singapore"),
                    tool_http_client=client,
                )
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                cursor = self.activate_session(coordinator, session_id)
                coordinator.host_event(
                    "tool_call",
                    session_id,
                    call_id=f"weather-{index}",
                    name="weather",
                    arguments=json.dumps(arguments),
                )
                command = coordinator.command_after(cursor)
                output = json.loads(command["output"])
                self.assertEqual(command["type"], "tool_result")
                self.assertEqual(output["status"], "success")
                self.assertTrue(output["data"]["location"].startswith(expected_location))
                self.assertEqual(output["data"]["intent"], expected_intent)
                self.assertEqual(client.calls[0][1]["name"], expected_location)
                report_text = json.dumps(coordinator.report(), ensure_ascii=False)
                self.assertNotIn(expected_location, report_text)
                self.assertNotIn(f"weather-{index}", report_text)

    def test_realtime_weather_provider_failure_returns_bounded_non_speculative_output(self):
        lease = FakeLease()
        client = FakeJsonClient([ProviderError("timeout", "request timed out")])
        coordinator = HandoffCoordinator(
            lease,
            session_ids=lambda: "session-1",
            tool_provider_config=ProviderConfig(default_location="Singapore"),
            tool_http_client=client,
        )
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        cursor = self.activate_session(coordinator, session_id)
        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="weather-failure",
            name="weather",
            arguments=json.dumps({"intent": "current"}),
        )
        output = json.loads(coordinator.command_after(cursor)["output"])
        self.assertEqual(output["status"], "error")
        self.assertIn("could not get weather data", output["answer"])
        self.assertEqual(output["data"]["provider_error"], "timeout")
        self.assertNotIn("temperature", json.dumps(output))
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_realtime_local_time_reuses_injected_host_clock_and_rejects_arguments(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(
            lease,
            session_ids=lambda: "session-1",
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
        session_id = coordinator.begin_handoff()
        cursor = self.activate_session(coordinator, session_id)
        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="time-success",
            name="local_time",
            arguments="{}",
        )
        command = coordinator.command_after(cursor)
        output = json.loads(command["output"])
        self.assertEqual(output["status"], "success")
        self.assertEqual(output["data"]["date"], "2026-07-28")
        self.assertEqual(output["data"]["time"], "16:42")
        self.assertEqual(output["data"]["timezone"], "+08")
        self.assertNotIn("time-success", json.dumps(coordinator.report()))

        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="time-invalid",
            name="local_time",
            arguments=json.dumps({"timezone": "Asia/Tokyo"}),
        )
        invalid = json.loads(
            coordinator.command_after(command["command_id"])["output"]
        )
        self.assertEqual(invalid["status"], "error")
        self.assertIn("Local time arguments were invalid", invalid["answer"])

    def test_realtime_fx_reuses_provider_conversion_defaults_and_redacts_content(self):
        cases = (
            (
                {"amount": 100, "base": "USD", "quote": "SGD"},
                {"date": "2026-07-28", "base": "USD", "quote": "SGD", "rate": 1.35},
                100.0,
                "USD",
                "SGD",
                135.0,
                "",
            ),
            (
                {},
                {"date": "2026-07-28", "base": "USD", "quote": "SGD", "rate": 1.35},
                1.0,
                "USD",
                "SGD",
                1.35,
                "Defaulted base to USD. Defaulted quote to SGD.",
            ),
        )
        for index, (
            arguments,
            response,
            amount,
            base,
            quote,
            converted,
            default_note,
        ) in enumerate(cases):
            with self.subTest(arguments=arguments):
                lease = FakeLease()
                client = FakeJsonClient([response])
                coordinator = HandoffCoordinator(
                    lease,
                    session_ids=lambda: "session-1",
                    tool_provider_config=ProviderConfig(
                        default_base_currency="USD",
                        http_timeout_seconds=2.5,
                    ),
                    tool_http_client=client,
                )
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                cursor = self.activate_session(coordinator, session_id)
                call_id = f"fx-private-{index}"
                coordinator.host_event(
                    "tool_call",
                    session_id,
                    call_id=call_id,
                    name="fx",
                    arguments=json.dumps(arguments),
                )
                output = json.loads(coordinator.command_after(cursor)["output"])
                self.assertEqual(output["status"], "success")
                self.assertEqual(output["data"]["amount"], amount)
                self.assertEqual(output["data"]["base"], base)
                self.assertEqual(output["data"]["quote"], quote)
                self.assertEqual(output["data"]["converted_amount"], converted)
                self.assertEqual(output["data"]["date"], "2026-07-28")
                self.assertIn("Frankfurter reference rate", output["answer"])
                self.assertIn("Not a bank cash or trade quote", output["answer"])
                if default_note:
                    self.assertIn(default_note, output["answer"])
                self.assertIn("/USD/SGD", client.calls[0][0])
                report_text = json.dumps(coordinator.report())
                self.assertNotIn(call_id, report_text)
                self.assertNotIn(str(converted), report_text)

    def test_realtime_fx_rejects_invalid_and_same_currency_without_inventing_a_rate(self):
        cases = (
            ({"amount": -1, "base": "USD", "quote": "SGD"}, "FX arguments were invalid."),
            ({"amount": 1_000_000_001, "base": "USD", "quote": "SGD"}, "FX arguments were invalid."),
            ({"amount": 1, "base": "CHF", "quote": "SGD"}, "FX arguments were invalid."),
            ({"amount": 1, "base": "usd", "quote": "SGD"}, "FX arguments were invalid."),
            ({"amount": 1, "base": "USD", "quote": "USD"}, "base and quote are both USD"),
            ({"amount": 1, "base": "USD", "quote": "SGD", "extra": True}, "FX arguments were invalid."),
        )
        for index, (arguments, expected) in enumerate(cases):
            with self.subTest(arguments=arguments):
                lease = FakeLease()
                client = FakeJsonClient([])
                coordinator = HandoffCoordinator(
                    lease,
                    session_ids=lambda: "session-1",
                    tool_http_client=client,
                )
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                cursor = self.activate_session(coordinator, session_id)
                coordinator.host_event(
                    "tool_call",
                    session_id,
                    call_id=f"fx-invalid-{index}",
                    name="fx",
                    arguments=json.dumps(arguments),
                )
                output = json.loads(coordinator.command_after(cursor)["output"])
                self.assertEqual(output["status"], "error")
                self.assertIn(expected, output["answer"])
                self.assertNotIn("rate", output.get("data", {}))
                self.assertEqual(client.calls, [])
                self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_realtime_fx_provider_failure_returns_bounded_structured_error(self):
        lease = FakeLease()
        client = FakeJsonClient([ProviderError("timeout", "request timed out")])
        coordinator = HandoffCoordinator(
            lease,
            session_ids=lambda: "session-1",
            tool_http_client=client,
        )
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        cursor = self.activate_session(coordinator, session_id)
        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="fx-failure",
            name="fx",
            arguments=json.dumps({"amount": 100, "base": "USD", "quote": "SGD"}),
        )
        output = json.loads(coordinator.command_after(cursor)["output"])
        self.assertEqual(output["status"], "error")
        self.assertEqual(output["data"]["provider_error"], "timeout")
        self.assertNotIn("rate", output["data"])
        self.assertLessEqual(len(json.dumps(output)), 4096)
        self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_realtime_stock_reuses_finnhub_quote_and_redacts_symbol_price_and_key(self):
        lease = FakeLease()
        client = FakeJsonClient(
            [
                {
                    "c": 193.12,
                    "d": 1.23,
                    "dp": 0.64,
                    "h": 194.0,
                    "l": 190.0,
                    "o": 191.0,
                    "pc": 191.89,
                    "t": 1783306800,
                }
            ]
        )
        coordinator = HandoffCoordinator(
            lease,
            session_ids=lambda: "session-1",
            tool_provider_config=ProviderConfig(
                finnhub_api_key="private-finnhub-key",
                http_timeout_seconds=2.5,
            ),
            tool_http_client=client,
        )
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        cursor = self.activate_session(coordinator, session_id)
        coordinator.host_event(
            "tool_call",
            session_id,
            call_id="stock-private-call",
            name="stock",
            arguments=json.dumps({"symbol": "AAPL"}),
        )
        output = json.loads(coordinator.command_after(cursor)["output"])
        self.assertEqual(output["status"], "success")
        self.assertEqual(output["data"]["symbol"], "AAPL")
        self.assertEqual(output["data"]["current_price"], 193.12)
        self.assertEqual(output["data"]["time"], "2026-07-06 03:00 UTC")
        self.assertIn("market data may be delayed", output["answer"])
        self.assertIn("not trading advice", output["answer"])
        self.assertEqual(
            client.calls,
            [
                (
                    "https://api.finnhub.io/api/v1/quote",
                    {"symbol": "AAPL", "token": "private-finnhub-key"},
                )
            ],
        )
        report_text = json.dumps(coordinator.report())
        for private in ("stock-private-call", "AAPL", "193.12", "private-finnhub-key"):
            self.assertNotIn(private, report_text)

    def test_realtime_stock_rejects_malformed_tickers_without_provider_call(self):
        cases = (
            {},
            {"symbol": ""},
            {"symbol": "aapl"},
            {"symbol": "TOOLONG"},
            {"symbol": "AAPL;DROP"},
            {"symbol": "AAPL", "extra": True},
        )
        for index, arguments in enumerate(cases):
            with self.subTest(arguments=arguments):
                lease = FakeLease()
                client = FakeJsonClient([])
                coordinator = HandoffCoordinator(
                    lease,
                    session_ids=lambda: "session-1",
                    tool_provider_config=ProviderConfig(
                        finnhub_api_key="private-finnhub-key"
                    ),
                    tool_http_client=client,
                )
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                cursor = self.activate_session(coordinator, session_id)
                coordinator.host_event(
                    "tool_call",
                    session_id,
                    call_id=f"stock-invalid-{index}",
                    name="stock",
                    arguments=json.dumps(arguments),
                )
                output = json.loads(coordinator.command_after(cursor)["output"])
                self.assertEqual(output["status"], "error")
                self.assertIn("Stock arguments were invalid", output["answer"])
                self.assertEqual(client.calls, [])
                self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_realtime_stock_missing_key_and_provider_failure_are_non_speculative(self):
        cases = (
            (
                ProviderConfig(finnhub_api_key=None),
                FakeJsonClient([]),
                "missing_credentials",
            ),
            (
                ProviderConfig(finnhub_api_key="private-finnhub-key"),
                FakeJsonClient([ProviderError("timeout", "request timed out")]),
                "timeout",
            ),
            (
                ProviderConfig(finnhub_api_key="private-finnhub-key"),
                FakeJsonClient(
                    [{"c": 0, "d": 0, "dp": 0, "h": 0, "l": 0, "o": 0, "pc": 0, "t": 0}]
                ),
                "unknown_symbol",
            ),
        )
        for index, (config, client, expected_error) in enumerate(cases):
            with self.subTest(expected_error=expected_error):
                lease = FakeLease()
                coordinator = HandoffCoordinator(
                    lease,
                    session_ids=lambda: "session-1",
                    tool_provider_config=config,
                    tool_http_client=client,
                )
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                cursor = self.activate_session(coordinator, session_id)
                coordinator.host_event(
                    "tool_call",
                    session_id,
                    call_id=f"stock-failure-{index}",
                    name="stock",
                    arguments=json.dumps({"symbol": "AAPL"}),
                )
                output = json.loads(coordinator.command_after(cursor)["output"])
                self.assertEqual(output["status"], "error")
                self.assertEqual(output["data"]["provider_error"], expected_error)
                self.assertNotIn("current_price", output["data"])
                self.assertLessEqual(len(json.dumps(output)), 4096)
                self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)

    def test_slow_realtime_weather_does_not_hold_lifecycle_lock_or_enqueue_late_result(self):
        started = threading.Event()
        release = threading.Event()

        class BlockingClient:
            def get_json(self, _url: str, *, params=None, timeout_seconds: float):
                started.set()
                release.wait(1.0)
                return weather_location()

        lease = FakeLease()
        coordinator = HandoffCoordinator(
            lease,
            session_ids=lambda: "session-1",
            tool_http_client=BlockingClient(),
        )
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        cursor = self.activate_session(coordinator, session_id)
        worker = threading.Thread(
            target=lambda: coordinator.host_event(
                "tool_call",
                session_id,
                call_id="weather-slow",
                name="weather",
                arguments=json.dumps({"intent": "current"}),
            )
        )
        worker.start()
        self.assertTrue(started.wait(0.5))
        coordinator.request_stop("test")
        stop = coordinator.command_after(cursor)
        self.assertEqual(stop["type"], "stop")
        release.set()
        worker.join(1.0)
        self.assertFalse(worker.is_alive())
        self.assertIsNone(coordinator.command_after(stop["command_id"]))
        report_text = json.dumps(coordinator.report())
        self.assertIn("host_tool_result_ignored", report_text)
        self.assertNotIn("weather-slow", report_text)

    def test_end_conversation_tool_requests_one_existing_stop_without_output(self):
        lease = FakeLease()
        coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        cursor = self.activate_session(coordinator, session_id)

        result = coordinator.host_event(
            "tool_call",
            session_id,
            call_id="end-call",
            name="end_conversation",
            arguments="{}",
        )

        self.assertEqual(result, "stopping")
        self.assertEqual(coordinator.state, HandoffState.HOST_STOPPING)
        command = coordinator.command_after(cursor)
        self.assertEqual(command["type"], "stop")
        self.assertEqual(command["reason"], "end_phrase")
        self.assertNotIn("output", command)
        self.assertEqual(
            coordinator.host_event(
                "tool_call",
                session_id,
                call_id="end-call",
                name="end_conversation",
                arguments="{}",
            ),
            "stopping",
        )
        self.assertIsNone(coordinator.command_after(command["command_id"]))
        report_text = json.dumps(coordinator.report())
        self.assertIn("host_end_conversation_tool", report_text)
        for private in ("end-call", "arguments"):
            self.assertNotIn(private, report_text)

    def test_end_conversation_tool_rejects_nonempty_or_malformed_arguments(self):
        for index, arguments in enumerate(
            (
                "not-json",
                "[]",
                json.dumps({"reason": "goodbye"}),
                " " * (MAX_TOOL_ARGUMENT_CHARS + 1),
            )
        ):
            with self.subTest(arguments=arguments):
                lease = FakeLease()
                coordinator = HandoffCoordinator(lease, session_ids=lambda: "session-1")
                coordinator.host_event("armed")
                session_id = coordinator.begin_handoff()
                self.activate_session(coordinator, session_id)
                result = coordinator.host_event(
                    "tool_call",
                    session_id,
                    call_id=f"bad-end-{index}",
                    name="end_conversation",
                    arguments=arguments,
                )
                self.assertEqual(result, "accepted")
                self.assertEqual(coordinator.state, HandoffState.HOST_ACTIVE)
                self.assertIsNone(coordinator.command_after(2))
                report_text = json.dumps(coordinator.report())
                self.assertIn("host_end_conversation_tool_ignored", report_text)
                self.assertNotIn(arguments, report_text)

    def test_fixture_audio_is_bounded_session_scoped_and_excluded_from_report(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        cursor = self.activate_session(coordinator, session_id)
        encoded = "AQACAA=="
        coordinator.request_fixture_audio("turn-1", encoded)
        command = coordinator.command_after(cursor)
        self.assertEqual(command["type"], "fixture_audio")
        self.assertEqual(command["fixture_name"], "turn-1")
        self.assertEqual(command["audio"], encoded)
        report_text = json.dumps(coordinator.report())
        self.assertNotIn(encoded, report_text)
        with self.assertRaisesRegex(HandoffError, "name"):
            coordinator.request_fixture_audio("wake", encoded)
        with self.assertRaisesRegex(HandoffError, "payload"):
            coordinator.request_fixture_audio("turn-2", "not-base64")

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
        self.assertIn("Enable voice assistant", html)
        self.assertIn('data-ui-state="ready"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn("End conversation", html)
        self.assertNotIn('id="events"', html)
        self.assertNotIn('id="settings"', html)
        self.assertNotIn('id="long"', html)
        stylesheet = server.resolve_static("/styles.css")[0].decode()
        self.assertIn("prefers-reduced-motion: reduce", stylesheet)
        self.assertIn("button:focus-visible", stylesheet)
        self.assertIn("[hidden]", stylesheet)
        for state in (
            '"wake-ready"',
            "connecting",
            "listening",
            "thinking",
            "speaking",
            "stopping",
            "error",
        ):
            self.assertIn(state, javascript)
        self.assertIn('setUiState("listening")', javascript)
        self.assertIn('setUiState("speaking")', javascript)
        self.assertIn('setUiState("thinking")', javascript)
        for text in ("getUserMedia", "/api/command?after=", "host_id", "echoCancellation:{exact:true}", "track.stop()", "peer.close()"):
            self.assertIn(text, javascript)
        self.assertIn("REMOTE_AUDIO_VOLUME=0.1", javascript)
        self.assertIn("sessionConfig.output_volume", javascript)
        for text in (
            'advertised.includes("all")',
            'echoCancellation:{exact:"all"}',
            '"output_audio_buffer.started"',
            '"output_audio_buffer.stopped"',
            'hostEvent("playback_started")',
            'hostEvent("playback_stopped")',
            "echoCancellationRequested:echoPreference.requested",
            "echoCancellationAllSupported:echoPreference.allSupported",
            "inputNoiseReduction:sessionConfig.input_noise_reduction",
        ):
            self.assertIn(text, javascript)
        for text in (
            "createMediaStreamSource(mediaStream)",
            "getFloatTimeDomainData",
            'assistantSpeaking?"remote_playback":"no_remote_playback"',
            'hostEvent("input_level"',
            "INPUT_LEVEL_WINDOW_SAMPLES=5",
            "stopInputLevels()",
            "function skipInputLevels(timing)",
            "if(command.input_level_diagnostics===true)startInputLevels(stream,handoffTiming)",
            "else skipInputLevels(handoffTiming)",
            "webrtc_negotiation_failed",
            'response.headers.get("x-request-id")',
            'response.headers.get("retry-after")',
            'response.headers.get("x-ratelimit-remaining-requests")',
            'response.headers.get("x-ratelimit-reset-requests")',
            "error.safeDiagnostic=detail",
            'type:"input_audio"',
            'hostEvent("fixture_submitted")',
            'command.type==="fixture_audio"',
            "handoffTimingSummary",
            'hostEvent("handoff_timing"',
            "command_to_token_ms",
            "token_ms",
            "microphone_ms",
            "peer_setup_ms",
            "microphone_reporting_ms",
            "audio_analysis_setup_ms",
            "input_level_cleanup_ms",
            "audio_context_creation_ms",
            "analyser_setup_ms",
            "media_stream_source_creation_ms",
            "source_connection_ms",
            "monitor_startup_ms",
            "peer_connection_setup_ms",
            "offer_creation_ms",
            "local_description_ms",
            "negotiation_ms",
            "session_configuration_ms",
            "data_channel_open_ms",
            "session_created_after_data_channel_open_ms",
            "total_browser_ready_ms",
            "dc.onopen",
            "track.enabled=false;inputTrack=track",
            'hostEvent("session_configured")',
            'command.type==="enable_input"',
            'inputTrack.enabled=true',
            'hostEvent("connected")',
            'log("input_ready")',
        ):
            self.assertIn(text, javascript)
        self.assertLess(
            javascript.index("track.enabled=false;inputTrack=track"),
            javascript.index("pc.addTrack(track,stream)"),
        )
        self.assertLess(
            javascript.index('hostEvent("session_configured")'),
            javascript.index('inputTrack.enabled=true'),
        )
        self.assertEqual(javascript.count("new AudioContextClass()"), 1)
        self.assertNotIn("JSON.stringify(payload)", javascript.split("async function negotiationFailure", 1)[1].split("function flushInputLevels", 1)[0])
        for text in (
            "async function forwardToolCall",
            'result.status==="stopping"',
            'await stop("end_phrase")',
            'response.function_call_arguments.done',
            'item.type==="function_call"',
            'type:"function_call_output"',
        ):
            self.assertIn(text, javascript)
        for forbidden_tool in ('name:"weather"', 'name:"stock"', 'name:"fx"'):
            self.assertNotIn(forbidden_tool, javascript)
        self.assertNotIn("transcript decides", javascript)
        for forbidden in ("response.cancel", "conversation.item.truncate", "output_audio_buffer.clear"):
            self.assertNotIn(forbidden, javascript)
        for forbidden in (
            "OPENAI_API_KEY",
            "/token",
            "client_secrets",
            "session.update",
            "session.updated",
            "api.openai.com",
            "Authorization:",
        ):
            self.assertNotIn(forbidden, javascript)
        self.assertIn('fetch("/session"', javascript)
        self.assertIn('event.type==="session.created"', javascript)
        self.assertIn("tokenStarted=handoffTiming.tokenAcquired=handoffTiming.commandReceived", javascript)
        self.assertIn("without another browser click", guidance)
        self.assertIn("five start/stop cycles", guidance)

    def test_loopback_and_unified_call_redaction(self):
        with self.assertRaisesRegex(server.HostServerError, "loopback"):
            server.build_server("0.0.0.0", 0)
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeSDPResponse("v=0\r\no=answer")

        result = server.create_realtime_call(
            api_key="sk-fake-standard",
            sdp="v=0\r\no=offer",
            session={"type": "realtime", "model": "model-test"},
            urlopen=fake_urlopen,
            boundary="test-boundary",
        )
        request = captured["request"]
        body = request.data.decode()
        self.assertEqual(result, "v=0\r\no=answer")
        self.assertEqual(request.full_url, server.REALTIME_CALLS_URL)
        self.assertEqual(request.headers["Authorization"], "Bearer sk-fake-standard")
        self.assertEqual(
            request.headers["Content-type"],
            "multipart/form-data; boundary=test-boundary",
        )
        self.assertIn('name="sdp"', body)
        self.assertIn("v=0\r\no=offer", body)
        self.assertIn('name="session"', body)
        self.assertIn('{"type":"realtime","model":"model-test"}', body)
        self.assertNotIn("sk-fake-standard", body)

    def test_unified_session_uses_complete_validated_configuration(self):
        settings = SimpleNamespace(
            realtime_model="model-test",
            realtime_voice="alloy",
            realtime_server_vad_enabled=True,
            realtime_server_vad_threshold=0.8,
            realtime_input_noise_reduction="far_field",
            realtime_input_transcription_enabled=True,
            transcribe_model="gpt-4o-mini-transcribe",
        )
        session = server.build_realtime_session_config(settings)
        self.assertEqual(session["model"], "model-test")
        self.assertEqual(session["output_modalities"], ["audio"])
        self.assertEqual(session["audio"]["output"], {"voice": "alloy"})
        self.assertEqual(
            session["audio"]["input"],
            {
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.8,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                    "create_response": True,
                    "interrupt_response": True,
                },
                "noise_reduction": {"type": "far_field"},
                "transcription": {"model": "gpt-4o-mini-transcribe"},
            },
        )
        self.assertEqual(
            [tool["name"] for tool in session["tools"]],
            ["calculator", "weather", "local_time", "fx", "stock", "end_conversation"],
        )
        weather = session["tools"][1]
        self.assertEqual(weather["parameters"]["required"], ["intent"])
        self.assertFalse(weather["parameters"]["additionalProperties"])
        self.assertEqual(
            weather["parameters"]["properties"]["intent"]["enum"],
            ["current", "today", "tomorrow"],
        )
        local_time = session["tools"][2]
        self.assertEqual(local_time["parameters"]["properties"], {})
        self.assertFalse(local_time["parameters"]["additionalProperties"])
        fx = session["tools"][3]
        self.assertFalse(fx["parameters"]["additionalProperties"])
        self.assertEqual(
            fx["parameters"]["properties"]["amount"],
            {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": 1_000_000_000,
                "description": "Positive amount to convert; omit to use 1.",
            },
        )
        self.assertEqual(
            fx["parameters"]["properties"]["base"]["enum"],
            ["USD", "SGD", "CNY", "EUR", "JPY", "HKD", "GBP", "AUD"],
        )
        self.assertEqual(
            fx["parameters"]["properties"]["quote"]["enum"],
            ["USD", "SGD", "CNY", "EUR", "JPY", "HKD", "GBP", "AUD"],
        )
        stock = session["tools"][4]
        self.assertFalse(stock["parameters"]["additionalProperties"])
        self.assertEqual(stock["parameters"]["required"], ["symbol"])
        self.assertEqual(
            stock["parameters"]["properties"]["symbol"],
            {
                "type": "string",
                "pattern": "^[A-Z]{1,5}(?:\\.[A-Z])?$",
                "maxLength": 7,
                "description": "One uppercase stock ticker, for example AAPL or BRK.B.",
            },
        )
        self.assertIn("# Language", session["instructions"])
        self.assertIn("concise, natural Simplified Chinese", session["instructions"])

    def test_arm_time_settings_expose_only_safe_browser_values(self):
        responses: list[tuple[HTTPStatus, dict[str, object]]] = []
        handler = object.__new__(server.HostRequestHandler)
        handler.path = "/api/realtime-settings"
        handler._json = lambda status, payload: responses.append((status, dict(payload)))
        settings = SimpleNamespace(
            openai_api_key="sk-private",
            realtime_model="model-test",
            realtime_voice="marin",
            realtime_output_volume=0.3,
            realtime_server_vad_enabled=True,
            realtime_server_vad_threshold=0.8,
            realtime_input_noise_reduction="far_field",
            realtime_input_transcription_enabled=True,
            transcribe_model="gpt-4o-mini-transcribe",
        )
        with patch.object(server, "load_settings", return_value=settings):
            handler.do_GET()

        self.assertEqual(responses[0][0], HTTPStatus.OK)
        self.assertEqual(
            responses[0][1],
            {"input_noise_reduction": "far_field", "output_volume": 0.3},
        )
        self.assertNotIn("sk-private", json.dumps(responses))

    def test_session_endpoint_rejects_unbounded_or_non_sdp_payloads(self):
        for content_type, body, message in (
            ("application/json", b"v=0", "content type"),
            ("application/sdp", b"not-sdp", "invalid"),
            ("application/sdp", b"v=0" + b"x" * server.MAX_SDP_BYTES, "size"),
        ):
            handler = object.__new__(server.HostRequestHandler)
            handler.headers = {
                "Content-Type": content_type,
                "Content-Length": str(len(body)),
            }
            handler.rfile = BytesIO(body)
            with self.assertRaisesRegex(server.HostServerError, message):
                handler._read_sdp()

    def test_capture_and_playback_evidence_is_allowlisted_without_content(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event(
            "microphone_acquired",
            session_id,
            echoCancellation="all",
            echoCancellationRequested="all",
            echoCancellationAllSupported=True,
            noiseSuppression=True,
            autoGainControl=True,
            inputNoiseReduction="far_field",
            outputVolume=0.3,
            transcript="must-not-survive",
        )
        self.activate_session(coordinator, session_id)
        coordinator.host_event("playback_started", session_id, answer="must-not-survive")
        coordinator.host_event("playback_stopped", session_id)

        report = coordinator.report()
        microphone = next(event for event in report["events"] if event["type"] == "host_microphone_acquired")
        self.assertEqual(microphone["echoCancellationRequested"], "all")
        self.assertTrue(microphone["echoCancellationAllSupported"])
        self.assertEqual(microphone["inputNoiseReduction"], "far_field")
        self.assertEqual(microphone["outputVolume"], 0.3)
        self.assertNotIn("must-not-survive", json.dumps(report))
        self.assertIn("host_playback_started", [event["type"] for event in report["events"]])
        self.assertIn("host_playback_stopped", [event["type"] for event in report["events"]])

    def test_idle_timeout_waits_for_playback_stop_and_restarts_full_window(self):
        now = [0.0]
        lease = FakeLease()
        ids = iter(("session-1", "session-2"))
        coordinator = HandoffCoordinator(
            lease,
            clock=lambda: now[0],
            session_ids=lambda: next(ids),
        )
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        self.activate_session(coordinator, session_id)

        coordinator.host_event("playback_started", session_id)
        coordinator.host_event("playback_started", session_id)
        now[0] = 120.0
        self.assertIsNone(
            coordinator.timeout_reason(idle_seconds=60.0, max_duration_seconds=600.0)
        )

        coordinator.host_event("playback_stopped", session_id)
        now[0] = 179.999
        self.assertIsNone(
            coordinator.timeout_reason(idle_seconds=60.0, max_duration_seconds=600.0)
        )
        now[0] = 180.0
        self.assertEqual(
            coordinator.timeout_reason(idle_seconds=60.0, max_duration_seconds=600.0),
            "idle_timeout",
        )

        coordinator.request_stop("idle_timeout")
        coordinator.host_event("stopped", session_id)
        next_session_id = coordinator.begin_handoff()
        self.activate_session(coordinator, next_session_id)
        now[0] = 240.0
        self.assertEqual(
            coordinator.timeout_reason(idle_seconds=60.0, max_duration_seconds=600.0),
            "idle_timeout",
        )

    def test_max_duration_still_closes_when_playback_stop_is_missing(self):
        now = [0.0]
        lease = FakeLease()
        coordinator = HandoffCoordinator(
            lease,
            clock=lambda: now[0],
            session_ids=lambda: "session-1",
        )
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        self.activate_session(coordinator, session_id)
        coordinator.host_event("playback_started", session_id)

        now[0] = 599.999
        self.assertIsNone(
            coordinator.timeout_reason(idle_seconds=60.0, max_duration_seconds=600.0)
        )
        now[0] = 600.0
        self.assertEqual(
            coordinator.timeout_reason(idle_seconds=60.0, max_duration_seconds=600.0),
            "max_duration",
        )

    def test_report_is_bounded_and_redacts_content_and_tool_secrets(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        self.activate_session(coordinator, session_id)
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

    def test_input_level_events_are_strictly_validated_rounded_and_bounded(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        self.activate_session(coordinator, session_id)
        coordinator.host_event(
            "input_level",
            session_id,
            phase="no_remote_playback",
            rms=0.012345,
            peak=0.234567,
            sampleCount=5,
            transcript="must-not-survive",
        )
        level = next(
            event
            for event in coordinator.report()["events"]
            if event["type"] == "host_input_level"
        )
        self.assertEqual(
            level,
            {
                "at_ms": 1250,
                "type": "host_input_level",
                "session_id": session_id,
                "phase": "no_remote_playback",
                "rms": 0.0123,
                "peak": 0.2346,
                "sampleCount": 5,
            },
        )
        self.assertNotIn("transcript", json.dumps(coordinator.report()))

        invalid_details = (
            {"phase": "unknown", "rms": 0.1, "peak": 0.2, "sampleCount": 5},
            {"phase": "remote_playback", "rms": -0.1, "peak": 0.2, "sampleCount": 5},
            {"phase": "remote_playback", "rms": 0.1, "peak": 1.1, "sampleCount": 5},
            {"phase": "remote_playback", "rms": 0.1, "peak": 0.2, "sampleCount": 0},
            {"phase": "remote_playback", "rms": True, "peak": 0.2, "sampleCount": 5},
        )
        for detail in invalid_details:
            with self.subTest(detail=detail), self.assertRaisesRegex(HandoffError, "Input-level"):
                coordinator.host_event("input_level", session_id, **detail)

    def test_handoff_timing_is_complete_bounded_private_and_single_shot(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        coordinator.record_local_timing_marker("wake_confirmed")
        coordinator.record_local_timing_marker("ack_started")
        coordinator.record_local_timing_marker("ack_completed")
        session_id = coordinator.begin_handoff()
        timing = {
            "command_to_token_ms": 0,
            "token_ms": 0,
            "microphone_ms": 300,
            "peer_setup_ms": 20,
            "microphone_reporting_ms": 2,
            "audio_analysis_setup_ms": 1,
            "input_level_cleanup_ms": 0,
            "audio_context_creation_ms": 1,
            "analyser_setup_ms": 0,
            "media_stream_source_creation_ms": 0,
            "source_connection_ms": 0,
            "monitor_startup_ms": 0,
            "peer_connection_setup_ms": 4,
            "offer_creation_ms": 5,
            "local_description_ms": 8,
            "negotiation_ms": 900,
            "session_configuration_ms": 100,
            "data_channel_open_ms": 40,
            "session_created_after_data_channel_open_ms": 60,
            "total_browser_ready_ms": 1320,
        }
        coordinator.host_event(
            "handoff_timing",
            session_id,
            **timing,
        )
        recorded = next(
            event
            for event in coordinator.report()["events"]
            if event["type"] == "host_handoff_timing"
        )
        self.assertEqual({field: recorded[field] for field in timing}, timing)
        report_text = json.dumps(coordinator.report())
        self.assertNotIn('"transcript":', report_text)
        self.assertNotIn('"token":', report_text)
        with self.assertRaisesRegex(HandoffError, "already reported"):
            coordinator.host_event("handoff_timing", session_id, **timing)
        with self.assertRaisesRegex(HandoffError, "Local timing marker"):
            coordinator.record_local_timing_marker("private_marker")

        invalid = (
            ({key: value for key, value in timing.items() if key != "token_ms"}, "incomplete"),
            ({**timing, "transcript": "private", "token": "secret"}, "unsupported"),
            ({**timing, "token_ms": -1}, "outside"),
            ({**timing, "token_ms": 1, "total_browser_ready_ms": 1321}, "must be zero"),
            ({**timing, "command_to_token_ms": 1, "total_browser_ready_ms": 1321}, "must be zero"),
            ({**timing, "token_ms": True}, "integer"),
            ({**timing, "total_browser_ready_ms": 1}, "match"),
            ({**timing, "local_description_ms": 40}, "subphases"),
            ({**timing, "audio_context_creation_ms": 40}, "Audio analysis"),
            ({**timing, "data_channel_open_ms": 50}, "readiness"),
        )
        for detail, expected in invalid:
            with self.subTest(expected=expected):
                other, _other_lease = self.build_coordinator()
                other.host_event("armed")
                other_session = other.begin_handoff()
                with self.assertRaisesRegex(HandoffError, expected):
                    other.host_event("handoff_timing", other_session, **detail)

    def test_negotiation_error_retains_only_strict_safe_metadata(self):
        coordinator, _lease = self.build_coordinator()
        coordinator.host_event("armed")
        session_id = coordinator.begin_handoff()
        coordinator.host_event(
            "error",
            session_id,
            reason="webrtc_negotiation_failed",
            httpStatus=429,
            errorType="insufficient_quota",
            errorCode="insufficient_quota",
            requestId="req_safe_123",
            retryAfter="60",
            rateLimitRemainingRequests="0",
            rateLimitResetRequests="1m0s",
            responseBody='{"api_key":"sk-secret"}',
            transcript="private utterance",
        )
        error = next(
            event for event in coordinator.report()["events"] if event["type"] == "host_error"
        )
        self.assertEqual(
            error,
            {
                "at_ms": 1250,
                "type": "host_error",
                "session_id": session_id,
                "reason": "webrtc_negotiation_failed",
                "httpStatus": 429,
                "errorType": "insufficient_quota",
                "errorCode": "insufficient_quota",
                "requestId": "req_safe_123",
                "retryAfter": "60",
                "rateLimitRemainingRequests": "0",
                "rateLimitResetRequests": "1m0s",
            },
        )
        report_text = json.dumps(coordinator.report())
        self.assertNotIn("sk-secret", report_text)
        self.assertNotIn("private utterance", report_text)
        self.assertEqual(coordinator.state, HandoffState.HOST_STOPPING)

        coordinator2, _lease2 = self.build_coordinator()
        coordinator2.host_event("armed")
        session_id2 = coordinator2.begin_handoff()
        with self.assertRaisesRegex(HandoffError, "Negotiation"):
            coordinator2.host_event(
                "error",
                session_id2,
                reason="webrtc_negotiation_failed",
                httpStatus=429,
                errorCode="unsafe value with spaces",
            )


if __name__ == "__main__":
    unittest.main()

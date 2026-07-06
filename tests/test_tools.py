import unittest
from datetime import datetime, timedelta, timezone

from src.tools import answer_with_tools, execute_route, is_realtime_sensitive, route_text
from src.tools.providers import ProviderConfig
from src.tools.router import format_text_debug


class FakeJsonClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, url, *, params=None, timeout_seconds=5.0):
        self.calls.append((url, dict(params or {}), timeout_seconds))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def weather_geocoding_response():
    return {
        "results": [
            {
                "name": "Singapore",
                "country": "Singapore",
                "latitude": 1.29,
                "longitude": 103.85,
                "timezone": "Asia/Singapore",
            }
        ]
    }


def weather_daily_response():
    return {
        "daily": {
            "time": ["2026-07-06", "2026-07-07"],
            "temperature_2m_min": [25.0, 24.0],
            "temperature_2m_max": [32.0, 31.0],
            "apparent_temperature_max": [37.0, 36.0],
            "weather_code": [61, 63],
            "precipitation_sum": [1.0, 3.0],
            "rain_sum": [1.0, 3.0],
            "precipitation_probability_max": [55, 70],
        }
    }


class FakeChatClient:
    def __init__(self):
        self.calls = []

    def ask_chatgpt(self, text, history):
        self.calls.append(text)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": "chat answer"})
        return "chat answer"


class ToolRoutingTests(unittest.TestCase):
    def local_clock(self):
        return datetime(2026, 7, 6, 9, 8, tzinfo=timezone(timedelta(hours=8), name="+08"))

    def test_routes_calculator_and_evaluates_safe_expression(self):
        route = route_text("what is two plus two?")
        result = execute_route(route)

        self.assertEqual(route.category, "calculator")
        self.assertEqual(route.tool_name, "safe_calculator")
        self.assertEqual(route.params["expression"], "2 + 2")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.answer, "The answer is 4.")

    def test_rejects_unsafe_calculator_expression(self):
        route = route_text("__import__('os').system('date')")

        self.assertEqual(route.category, "none")

        result = execute_route(route)
        self.assertEqual(result.status, "noop")

    def test_routes_local_time_with_injectable_clock(self):
        route = route_text("现在几点")
        result = execute_route(route, now_provider=self.local_clock)

        self.assertEqual(route.category, "time")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.summary, "local time 2026-07-06 09:08 +08")
        self.assertIn("09:08", result.answer)

    def test_routes_weather_with_location_and_intent(self):
        route = route_text("tomorrow weather in Tokyo")

        self.assertEqual(route.category, "weather")
        self.assertEqual(route.params["intent"], "tomorrow")
        self.assertEqual(route.params["location"], "tokyo")

        chinese_route = route_text("明天东京天气怎么样")
        self.assertEqual(chinese_route.category, "weather")
        self.assertEqual(chinese_route.params["intent"], "tomorrow")
        self.assertEqual(chinese_route.params["location"], "东京")

    def test_routes_remaining_planned_provider_categories_to_not_configured(self):
        cases = {
            "美元兑新币汇率是多少": "fx",
            "苹果股价多少": "stock",
            "AAPL stock price": "stock",
        }

        for text, expected_category in cases.items():
            with self.subTest(text=text):
                route = route_text(text)
                result = execute_route(route)
                self.assertEqual(route.category, expected_category)
                self.assertEqual(result.status, "not_configured")
                self.assertIn("provider behavior is not implemented", result.answer)

    def test_weather_answer_path_uses_provider_and_skips_chat(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([weather_geocoding_response(), weather_daily_response()])
        history = []

        answer, route, result = answer_with_tools(
            "明天天气怎么样",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(default_location="Singapore"),
            http_client=client,
        )

        self.assertEqual(route.category, "weather")
        self.assertEqual(route.params["intent"], "tomorrow")
        self.assertEqual(result.status, "success")
        self.assertIn("Tomorrow in Singapore, Singapore", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_weather_provider_failure_does_not_fall_back_to_chat(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([{"results": []}])
        history = []

        answer, route, result = answer_with_tools(
            "weather in Atlantis",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(),
            http_client=client,
        )

        self.assertEqual(route.category, "weather")
        self.assertEqual(result.status, "error")
        self.assertIn("could not get weather data", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_stock_provider_route_reports_missing_finnhub_key(self):
        route = route_text("AAPL stock price")
        result = execute_route(route, provider_config=ProviderConfig(finnhub_api_key=None))

        self.assertEqual(route.category, "stock")
        self.assertEqual(result.status, "not_configured")
        self.assertEqual(result.summary, "stock market provider credentials are missing")
        self.assertIn("FINNHUB_API_KEY is missing", result.answer)
        self.assertNotIn("sk-", result.answer)

    def test_ambiguous_stock_like_phrase_does_not_route_to_stock(self):
        route = route_text("苹果怎么样")

        self.assertEqual(route.category, "none")
        self.assertTrue(is_realtime_sensitive("今天苹果怎么样"))

    def test_refuses_unsupported_realtime_without_chat_fallback(self):
        chat_client = FakeChatClient()
        history = []

        answer, route, result = answer_with_tools(
            "今天有什么新闻",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
        )

        self.assertEqual(route.category, "unsupported_realtime")
        self.assertEqual(result.status, "refused")
        self.assertIn("without a configured provider", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_latest_supported_provider_question_uses_planned_tool_not_refusal(self):
        route = route_text("latest AAPL stock price")
        result = execute_route(route)

        self.assertEqual(route.category, "stock")
        self.assertEqual(result.status, "not_configured")

    def test_none_route_uses_chat_when_tools_enabled(self):
        chat_client = FakeChatClient()
        history = []

        answer, route, result = answer_with_tools(
            "tell me a short joke",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
        )

        self.assertEqual(route.category, "none")
        self.assertIsNone(result)
        self.assertEqual(answer, "chat answer")
        self.assertEqual(chat_client.calls, ["tell me a short joke"])

    def test_tools_disabled_uses_chat_even_when_route_matches(self):
        chat_client = FakeChatClient()
        history = []

        answer, route, result = answer_with_tools(
            "2 + 2",
            chat_client=chat_client,
            history=history,
            tools_enabled=False,
        )

        self.assertEqual(route.category, "calculator")
        self.assertIsNone(result)
        self.assertEqual(answer, "chat answer")
        self.assertEqual(chat_client.calls, ["2 + 2"])

    def test_text_debug_prints_route_result_and_final_answer(self):
        debug = format_text_debug(
            "现在几点",
            now_provider=self.local_clock,
            provider_config=ProviderConfig(finnhub_api_key="fh-secret"),
        )

        self.assertIn("input=现在几点", debug)
        self.assertIn("route=time", debug)
        self.assertIn("tool=local_time", debug)
        self.assertIn("provider_config=", debug)
        self.assertIn("finnhub_api_key:configured", debug)
        self.assertNotIn("fh-secret", debug)
        self.assertIn("result_status=success", debug)
        self.assertIn("final_answer=The local time is 09:08", debug)

    def test_text_debug_can_show_mocked_weather_result(self):
        client = FakeJsonClient([weather_geocoding_response(), weather_daily_response()])

        debug = format_text_debug(
            "tomorrow weather",
            provider_config=ProviderConfig(default_location="Singapore"),
            http_client=client,
        )

        self.assertIn("route=weather", debug)
        self.assertIn("result_status=success", debug)
        self.assertIn("Open-Meteo forecast for 2026-07-07", debug)


if __name__ == "__main__":
    unittest.main()

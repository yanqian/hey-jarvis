import io
import socket
import unittest
import urllib.error

from src.tools.providers import (
    JsonHttpClient,
    OPEN_METEO_FORECAST_URL,
    OPEN_METEO_GEOCODING_URL,
    ProviderConfig,
    ProviderError,
    provider_config_from_settings,
    provider_error_result,
)
from src.tools.router import ToolRoute


class FakeResponse:
    def __init__(self, body, *, status=200):
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


class FakeSettings:
    weather_provider = "open-meteo"
    fx_provider = "frankfurter"
    stock_provider = "finnhub"
    tool_http_timeout_seconds = 3.5
    default_location = "Singapore"
    default_base_currency = "SGD"
    finnhub_api_key = "fh-secret"


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


def geocoding_response(**overrides):
    location = {
        "name": "Singapore",
        "country": "Singapore",
        "latitude": 1.29,
        "longitude": 103.85,
        "timezone": "Asia/Singapore",
    }
    location.update(overrides)
    return {"results": [location]}


def current_forecast_response():
    return {
        "current": {
            "time": "2026-07-06T10:00",
            "temperature_2m": 31.2,
            "apparent_temperature": 36.1,
            "weather_code": 3,
            "precipitation": 0.0,
            "rain": 0.0,
        }
    }


def daily_forecast_response():
    return {
        "daily": {
            "time": ["2026-07-06", "2026-07-07"],
            "temperature_2m_min": [25.0, 24.5],
            "temperature_2m_max": [32.0, 31.5],
            "apparent_temperature_max": [38.0, 36.0],
            "weather_code": [61, 80],
            "precipitation_sum": [1.2, 4.5],
            "rain_sum": [1.2, 4.5],
            "precipitation_probability_max": [60, 75],
        }
    }


class ToolProviderTests(unittest.TestCase):
    def test_provider_config_public_summary_never_exposes_secret(self):
        config = ProviderConfig(finnhub_api_key="fh-secret")

        self.assertTrue(config.finnhub_configured)
        self.assertEqual(config.public_summary()["finnhub_api_key"], "configured")
        self.assertNotIn("fh-secret", str(config.public_summary()))

    def test_provider_config_from_settings(self):
        config = provider_config_from_settings(FakeSettings())

        self.assertEqual(config.weather_provider, "open-meteo")
        self.assertEqual(config.fx_provider, "frankfurter")
        self.assertEqual(config.stock_provider, "finnhub")
        self.assertEqual(config.http_timeout_seconds, 3.5)
        self.assertEqual(config.default_location, "Singapore")
        self.assertEqual(config.default_base_currency, "SGD")
        self.assertEqual(config.finnhub_api_key, "fh-secret")

    def test_json_get_success_adds_query_params_and_timeout(self):
        calls = []

        def opener(request, *, timeout):
            calls.append((request.full_url, timeout, request.get_method()))
            return FakeResponse(b'{"ok": true, "value": 2}')

        result = JsonHttpClient(opener=opener).get_json(
            "https://example.test/api",
            params={"q": "a b", "limit": 2},
            timeout_seconds=1.25,
        )

        self.assertEqual(result, {"ok": True, "value": 2})
        self.assertEqual(calls, [("https://example.test/api?q=a+b&limit=2", 1.25, "GET")])

    def test_json_get_maps_http_error(self):
        def opener(request, *, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                503,
                "Service Unavailable",
                hdrs=None,
                fp=io.BytesIO(b""),
            )

        with self.assertRaises(ProviderError) as caught:
            JsonHttpClient(opener=opener).get_json("https://example.test/api")

        self.assertEqual(caught.exception.kind, "http_status")
        self.assertEqual(caught.exception.status_code, 503)

    def test_json_get_maps_status_code_without_http_error(self):
        def opener(request, *, timeout):
            return FakeResponse(b'{"error": true}', status=429)

        with self.assertRaises(ProviderError) as caught:
            JsonHttpClient(opener=opener).get_json("https://example.test/api")

        self.assertEqual(caught.exception.kind, "http_status")
        self.assertEqual(caught.exception.status_code, 429)

    def test_json_get_maps_timeout(self):
        def opener(request, *, timeout):
            raise socket.timeout("timed out")

        with self.assertRaises(ProviderError) as caught:
            JsonHttpClient(opener=opener).get_json("https://example.test/api")

        self.assertEqual(caught.exception.kind, "timeout")

    def test_json_get_maps_url_timeout_reason(self):
        def opener(request, *, timeout):
            raise urllib.error.URLError(TimeoutError("timed out"))

        with self.assertRaises(ProviderError) as caught:
            JsonHttpClient(opener=opener).get_json("https://example.test/api")

        self.assertEqual(caught.exception.kind, "timeout")

    def test_json_get_maps_network_error(self):
        def opener(request, *, timeout):
            raise urllib.error.URLError("network unreachable")

        with self.assertRaises(ProviderError) as caught:
            JsonHttpClient(opener=opener).get_json("https://example.test/api")

        self.assertEqual(caught.exception.kind, "network")
        self.assertIn("network unreachable", caught.exception.message)

    def test_json_get_maps_malformed_json(self):
        def opener(request, *, timeout):
            return FakeResponse(b"not json")

        with self.assertRaises(ProviderError) as caught:
            JsonHttpClient(opener=opener).get_json("https://example.test/api")

        self.assertEqual(caught.exception.kind, "malformed_json")

    def test_provider_error_maps_to_recoverable_tool_result(self):
        route = ToolRoute("weather", "weather_provider", {"query": "weather"})
        error = ProviderError("timeout", "provider request timed out")

        result = provider_error_result(route, error)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "weather provider error: timeout")
        self.assertIn("could not get weather data", result.answer)

    def test_open_meteo_current_weather_success(self):
        client = FakeJsonClient([geocoding_response(), current_forecast_response()])
        route = ToolRoute(
            "weather",
            "weather_provider",
            {"query": "weather in Singapore now", "location": "Singapore", "intent": "current"},
        )

        from src.tools import execute_route

        result = execute_route(
            route,
            provider_config=ProviderConfig(http_timeout_seconds=2.5),
            http_client=client,
        )

        self.assertEqual(result.status, "success")
        self.assertIn("Weather in Singapore, Singapore now", result.answer)
        self.assertEqual(result.data["source"], "open-meteo")
        self.assertEqual(result.data["location"], "Singapore, Singapore")
        self.assertEqual(result.data["time"], "2026-07-06T10:00")
        self.assertEqual(result.data["freshness"], "current at 2026-07-06T10:00")
        self.assertEqual(result.data["temperature_c"], 31.2)
        self.assertEqual(
            client.calls[0],
            (
                OPEN_METEO_GEOCODING_URL,
                {"name": "Singapore", "count": 1, "language": "en", "format": "json"},
                2.5,
            ),
        )
        self.assertEqual(client.calls[1][0], OPEN_METEO_FORECAST_URL)
        self.assertEqual(client.calls[1][1]["current"], "temperature_2m,apparent_temperature,weather_code,precipitation,rain")
        self.assertEqual(client.calls[1][1]["timezone"], "Asia/Singapore")

    def test_open_meteo_tomorrow_forecast_uses_daily_fields(self):
        client = FakeJsonClient([geocoding_response(name="Tokyo", country="Japan"), daily_forecast_response()])
        route = ToolRoute(
            "weather",
            "weather_provider",
            {"query": "tomorrow weather in Tokyo", "location": "Tokyo", "intent": "tomorrow"},
        )

        from src.tools import execute_route

        result = execute_route(route, provider_config=ProviderConfig(), http_client=client)

        self.assertEqual(result.status, "success")
        self.assertIn("Tomorrow in Tokyo, Japan", result.answer)
        self.assertIn("Open-Meteo forecast for 2026-07-07", result.answer)
        self.assertEqual(result.data["intent"], "tomorrow")
        self.assertEqual(result.data["time"], "2026-07-07")
        self.assertEqual(result.data["precipitation_probability_max_percent"], 75.0)

    def test_open_meteo_weather_uses_default_location_when_omitted(self):
        client = FakeJsonClient([geocoding_response(), daily_forecast_response()])
        route = ToolRoute("weather", "weather_provider", {"query": "明天天气怎么样", "intent": "tomorrow"})

        from src.tools import execute_route

        result = execute_route(
            route,
            provider_config=ProviderConfig(default_location="Singapore"),
            http_client=client,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(client.calls[0][1]["name"], "Singapore")
        self.assertEqual(result.data["intent"], "tomorrow")

    def test_open_meteo_no_geocoding_match_returns_structured_error(self):
        client = FakeJsonClient([{"results": []}])
        route = ToolRoute("weather", "weather_provider", {"query": "weather in Nowhere", "location": "Nowhere"})

        from src.tools import execute_route

        result = execute_route(route, provider_config=ProviderConfig(), http_client=client)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "weather provider error: no_location_match")
        self.assertEqual(result.data["provider_error"], "no_location_match")

    def test_open_meteo_missing_forecast_fields_returns_structured_error(self):
        client = FakeJsonClient([geocoding_response(), {"current": {"time": "2026-07-06T10:00"}}])
        route = ToolRoute("weather", "weather_provider", {"query": "weather in Singapore", "location": "Singapore"})

        from src.tools import execute_route

        result = execute_route(route, provider_config=ProviderConfig(), http_client=client)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "weather provider error: missing_forecast_fields")

    def test_non_open_meteo_weather_provider_remains_not_configured(self):
        route = ToolRoute("weather", "weather_provider", {"query": "weather", "intent": "current"})

        from src.tools import execute_route

        result = execute_route(route, provider_config=ProviderConfig(weather_provider="other-weather"))

        self.assertEqual(result.status, "not_configured")
        self.assertIn("provider behavior is not implemented", result.answer)


if __name__ == "__main__":
    unittest.main()

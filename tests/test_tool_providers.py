import io
import socket
import unittest
import urllib.error

from src.tools.providers import (
    JsonHttpClient,
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
        self.assertIn("could not reach", result.answer)


if __name__ == "__main__":
    unittest.main()

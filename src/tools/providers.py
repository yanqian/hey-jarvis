"""Shared provider configuration and HTTP JSON helpers for structured tools."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .router import (
    ROUTE_FX,
    ROUTE_STOCK,
    ROUTE_WEATHER,
    TOOL_STATUS_ERROR,
    ToolResult,
    ToolRoute,
)


DEFAULT_WEATHER_PROVIDER = "open-meteo"
DEFAULT_FX_PROVIDER = "frankfurter"
DEFAULT_STOCK_PROVIDER = "finnhub"
DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS = 5.0
DEFAULT_LOCATION = "Singapore"
DEFAULT_BASE_CURRENCY = "USD"

PROVIDER_ERROR_HTTP_STATUS = "http_status"
PROVIDER_ERROR_TIMEOUT = "timeout"
PROVIDER_ERROR_NETWORK = "network"
PROVIDER_ERROR_MALFORMED_JSON = "malformed_json"


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration shared by future network-backed tools."""

    weather_provider: str = DEFAULT_WEATHER_PROVIDER
    fx_provider: str = DEFAULT_FX_PROVIDER
    stock_provider: str = DEFAULT_STOCK_PROVIDER
    http_timeout_seconds: float = DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS
    default_location: str = DEFAULT_LOCATION
    default_base_currency: str = DEFAULT_BASE_CURRENCY
    finnhub_api_key: str | None = None

    @property
    def finnhub_configured(self) -> bool:
        return self.finnhub_api_key is not None

    def public_summary(self) -> Mapping[str, str | float]:
        """Return non-secret fields safe for diagnostics and debug output."""

        return {
            "weather_provider": self.weather_provider,
            "fx_provider": self.fx_provider,
            "stock_provider": self.stock_provider,
            "http_timeout_seconds": self.http_timeout_seconds,
            "default_location": self.default_location,
            "default_base_currency": self.default_base_currency,
            "finnhub_api_key": "configured" if self.finnhub_configured else "missing",
        }


@dataclass(frozen=True)
class ProviderError(Exception):
    """Structured recoverable provider failure."""

    kind: str
    message: str
    status_code: int | None = None

    def __str__(self) -> str:
        if self.status_code is None:
            return f"{self.kind}: {self.message}"
        return f"{self.kind}: HTTP {self.status_code}: {self.message}"


UrlOpen = Callable[..., Any]


class JsonHttpClient:
    """Small JSON GET boundary for network-backed tools."""

    def __init__(self, opener: UrlOpen | None = None) -> None:
        self._opener = opener or urllib.request.urlopen

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float] | None = None,
        timeout_seconds: float = DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS,
    ) -> Any:
        request_url = _url_with_params(url, params or {})
        request = urllib.request.Request(request_url, method="GET")
        try:
            with self._opener(request, timeout=timeout_seconds) as response:
                status_code = int(getattr(response, "status", getattr(response, "code", 200)))
                body = response.read()
        except urllib.error.HTTPError as exc:
            exc.close()
            raise ProviderError(
                PROVIDER_ERROR_HTTP_STATUS,
                exc.reason or "provider returned an HTTP error",
                status_code=exc.code,
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ProviderError(PROVIDER_ERROR_TIMEOUT, "provider request timed out") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError | socket.timeout):
                raise ProviderError(PROVIDER_ERROR_TIMEOUT, "provider request timed out") from exc
            raise ProviderError(PROVIDER_ERROR_NETWORK, str(reason)) from exc

        if status_code >= 400:
            raise ProviderError(
                PROVIDER_ERROR_HTTP_STATUS,
                "provider returned an HTTP error",
                status_code=status_code,
            )

        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(PROVIDER_ERROR_MALFORMED_JSON, "provider returned malformed JSON") from exc


def provider_config_from_settings(settings: object) -> ProviderConfig:
    """Build provider config from a Settings-like object without importing config."""

    return ProviderConfig(
        weather_provider=str(getattr(settings, "weather_provider")),
        fx_provider=str(getattr(settings, "fx_provider")),
        stock_provider=str(getattr(settings, "stock_provider")),
        http_timeout_seconds=float(getattr(settings, "tool_http_timeout_seconds")),
        default_location=str(getattr(settings, "default_location")),
        default_base_currency=str(getattr(settings, "default_base_currency")),
        finnhub_api_key=getattr(settings, "finnhub_api_key"),
    )


def provider_error_result(route: ToolRoute, error: ProviderError) -> ToolResult:
    """Map a provider exception to a recoverable tool result."""

    label = _route_label(route)
    return ToolResult(
        TOOL_STATUS_ERROR,
        f"{label} provider error: {error.kind}",
        f"I could not reach the {label} provider: {error.message}",
        {
            "category": route.category,
            "provider_error": error.kind,
            "status_code": float(error.status_code) if error.status_code is not None else "",
        },
    )


def _url_with_params(url: str, params: Mapping[str, str | int | float]) -> str:
    if not params:
        return url
    query = urllib.parse.urlencode(params)
    separator = "&" if urllib.parse.urlsplit(url).query else "?"
    return f"{url}{separator}{query}"


def _route_label(route: ToolRoute) -> str:
    return {
        ROUTE_WEATHER: "weather",
        ROUTE_STOCK: "stock market",
        ROUTE_FX: "foreign exchange",
    }.get(route.category, route.category)

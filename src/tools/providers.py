"""Shared provider configuration and HTTP JSON helpers for structured tools."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Mapping

from .router import (
    FX_SUPPORTED_CURRENCIES,
    ROUTE_FX,
    ROUTE_STOCK,
    ROUTE_WEATHER,
    TOOL_STATUS_ERROR,
    TOOL_STATUS_SUCCESS,
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
PROVIDER_ERROR_NO_MATCH = "no_location_match"
PROVIDER_ERROR_MISSING_DATA = "missing_forecast_fields"
PROVIDER_ERROR_MISSING_RATE_FIELDS = "missing_rate_fields"
PROVIDER_ERROR_UNSUPPORTED_CURRENCY = "unsupported_currency"
PROVIDER_ERROR_SAME_CURRENCY = "same_currency"
PROVIDER_ERROR_INVALID_AMOUNT = "invalid_amount"

OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FRANKFURTER_RATE_URL_TEMPLATE = "https://api.frankfurter.dev/v2/rate/{base}/{quote}"
DEFAULT_QUOTE_CURRENCY = "SGD"


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
        f"I could not get {label} data: {error.message}",
        {
            "category": route.category,
            "provider_error": error.kind,
            "status_code": float(error.status_code) if error.status_code is not None else "",
        },
    )


def open_meteo_weather_result(
    route: ToolRoute,
    *,
    provider_config: ProviderConfig,
    http_client: JsonHttpClient,
) -> ToolResult:
    """Resolve a routed weather request through Open-Meteo geocoding and forecast APIs."""

    location_query = str(route.params.get("location") or provider_config.default_location).strip()
    intent = str(route.params.get("intent") or "current").strip().casefold()
    if intent not in {"current", "today", "tomorrow"}:
        intent = "current"
    if not location_query:
        raise ProviderError(PROVIDER_ERROR_NO_MATCH, "weather location is empty")

    location = _resolve_open_meteo_location(
        location_query,
        http_client=http_client,
        timeout_seconds=provider_config.http_timeout_seconds,
    )
    forecast = http_client.get_json(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "timezone": location.get("timezone") or "auto",
            "forecast_days": 2,
            "current": "temperature_2m,apparent_temperature,weather_code,precipitation,rain",
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weather_code,precipitation,rain",
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                "precipitation_sum,rain_sum,precipitation_probability_max"
            ),
        },
        timeout_seconds=provider_config.http_timeout_seconds,
    )
    if not isinstance(forecast, Mapping):
        raise ProviderError(PROVIDER_ERROR_MISSING_DATA, "Open-Meteo forecast response was not an object")

    if intent == "current":
        return _current_weather_result(location, forecast)
    return _daily_weather_result(location, forecast, intent=intent)


def frankfurter_fx_result(
    route: ToolRoute,
    *,
    provider_config: ProviderConfig,
    http_client: JsonHttpClient,
) -> ToolResult:
    """Resolve a routed FX request through Frankfurter's single-pair rate API."""

    amount = _fx_amount(route)
    base, quote, default_note = _fx_pair(route, provider_config)
    unsupported = str(route.params.get("unsupported_currency") or "").strip().upper()
    if unsupported:
        raise ProviderError(PROVIDER_ERROR_UNSUPPORTED_CURRENCY, f"{unsupported} is not supported by this FX tool")
    if base not in FX_SUPPORTED_CURRENCIES:
        raise ProviderError(PROVIDER_ERROR_UNSUPPORTED_CURRENCY, f"{base} is not supported by this FX tool")
    if quote not in FX_SUPPORTED_CURRENCIES:
        raise ProviderError(PROVIDER_ERROR_UNSUPPORTED_CURRENCY, f"{quote} is not supported by this FX tool")
    if base == quote:
        raise ProviderError(PROVIDER_ERROR_SAME_CURRENCY, f"base and quote are both {base}")

    url = FRANKFURTER_RATE_URL_TEMPLATE.format(base=base, quote=quote)
    data = http_client.get_json(url, timeout_seconds=provider_config.http_timeout_seconds)
    if not isinstance(data, Mapping):
        raise ProviderError(PROVIDER_ERROR_MISSING_RATE_FIELDS, "Frankfurter rate response was not an object")

    response_base = _fx_string_field(data, "base").upper()
    response_quote = _fx_string_field(data, "quote").upper()
    if response_base != base or response_quote != quote:
        raise ProviderError(PROVIDER_ERROR_MISSING_RATE_FIELDS, "Frankfurter returned an unexpected currency pair")
    rate_date = _fx_string_field(data, "date")
    rate = _fx_number_field(data, "rate")
    if rate <= 0:
        raise ProviderError(PROVIDER_ERROR_MISSING_RATE_FIELDS, "Frankfurter rate was not positive")

    converted = (amount * Decimal(str(rate))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    amount_text = _format_decimal(amount)
    converted_text = _format_decimal(converted)
    rate_text = _format_rate(rate)
    default_suffix = f" {default_note}" if default_note else ""
    answer = (
        f"{amount_text} {base} is about {converted_text} {quote} at Frankfurter reference rate "
        f"{rate_text} from {rate_date}.{default_suffix} Not a bank cash or trade quote."
    )
    summary = f"frankfurter {amount_text} {base} to {quote} = {converted_text} {quote}"
    return ToolResult(
        TOOL_STATUS_SUCCESS,
        summary,
        answer,
        {
            "category": ROUTE_FX,
            "source": "frankfurter",
            "amount": float(amount),
            "base": base,
            "quote": quote,
            "rate": rate,
            "converted_amount": float(converted),
            "date": rate_date,
            "freshness": f"latest available reference rate dated {rate_date}",
            "rate_type": "reference",
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


def _resolve_open_meteo_location(
    location_query: str,
    *,
    http_client: JsonHttpClient,
    timeout_seconds: float,
) -> Mapping[str, str | float]:
    data = http_client.get_json(
        OPEN_METEO_GEOCODING_URL,
        params={"name": location_query, "count": 1, "language": "en", "format": "json"},
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(data, Mapping):
        raise ProviderError(PROVIDER_ERROR_MISSING_DATA, "Open-Meteo geocoding response was not an object")
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise ProviderError(PROVIDER_ERROR_NO_MATCH, f"no Open-Meteo location match for {location_query}")
    first = results[0]
    if not isinstance(first, Mapping):
        raise ProviderError(PROVIDER_ERROR_MISSING_DATA, "Open-Meteo geocoding result was malformed")

    latitude = _number_field(first, "latitude", context="geocoding")
    longitude = _number_field(first, "longitude", context="geocoding")
    name = _string_field(first, "name", context="geocoding")
    country = first.get("country")
    admin1 = first.get("admin1")
    timezone = first.get("timezone")
    location_parts = [
        name,
        str(admin1).strip() if isinstance(admin1, str) and admin1.strip() and admin1 != name else "",
        str(country).strip() if isinstance(country, str) and country.strip() else "",
    ]
    return {
        "name": name,
        "normalized_location": ", ".join(part for part in location_parts if part),
        "latitude": latitude,
        "longitude": longitude,
        "timezone": str(timezone).strip() if isinstance(timezone, str) and timezone.strip() else "auto",
    }


def _current_weather_result(location: Mapping[str, str | float], forecast: Mapping[str, Any]) -> ToolResult:
    current = forecast.get("current")
    if not isinstance(current, Mapping):
        raise ProviderError(PROVIDER_ERROR_MISSING_DATA, "Open-Meteo current weather fields were missing")

    temperature = _number_field(current, "temperature_2m", context="current weather")
    apparent = _optional_number_field(current, "apparent_temperature")
    weather_code = _optional_number_field(current, "weather_code")
    precipitation = _optional_number_field(current, "precipitation")
    rain = _optional_number_field(current, "rain")
    observation_time = _string_field(current, "time", context="current weather")
    location_name = str(location["normalized_location"])
    condition = _weather_code_label(weather_code)

    precip_text = _precipitation_text(precipitation=precipitation, rain=rain, probability=None)
    feels_text = f", feels like {_format_temperature(apparent)}" if apparent is not None else ""
    answer = (
        f"Weather in {location_name} now: {_format_temperature(temperature)}{feels_text}, "
        f"{condition}, {precip_text}. Open-Meteo current at {observation_time}."
    )
    summary = f"open-meteo current weather {location_name} {_format_temperature(temperature)}"
    return ToolResult(
        TOOL_STATUS_SUCCESS,
        summary,
        answer,
        {
            "category": ROUTE_WEATHER,
            "location": location_name,
            "source": "open-meteo",
            "intent": "current",
            "time": observation_time,
            "freshness": f"current at {observation_time}",
            "temperature_c": temperature,
            "apparent_temperature_c": apparent if apparent is not None else "",
            "weather_code": weather_code if weather_code is not None else "",
            "precipitation_mm": precipitation if precipitation is not None else "",
            "rain_mm": rain if rain is not None else "",
        },
    )


def _daily_weather_result(
    location: Mapping[str, str | float],
    forecast: Mapping[str, Any],
    *,
    intent: str,
) -> ToolResult:
    daily = forecast.get("daily")
    if not isinstance(daily, Mapping):
        raise ProviderError(PROVIDER_ERROR_MISSING_DATA, "Open-Meteo daily forecast fields were missing")
    index = 1 if intent == "tomorrow" else 0
    date_text = _daily_value(daily, "time", index, context="daily forecast")
    min_temp = _daily_number(daily, "temperature_2m_min", index, context="daily forecast")
    max_temp = _daily_number(daily, "temperature_2m_max", index, context="daily forecast")
    apparent_max = _optional_daily_number(daily, "apparent_temperature_max", index)
    weather_code = _optional_daily_number(daily, "weather_code", index)
    precipitation = _optional_daily_number(daily, "precipitation_sum", index)
    rain = _optional_daily_number(daily, "rain_sum", index)
    probability = _optional_daily_number(daily, "precipitation_probability_max", index)
    location_name = str(location["normalized_location"])
    condition = _weather_code_label(weather_code)
    precip_text = _precipitation_text(precipitation=precipitation, rain=rain, probability=probability)
    day_label = "tomorrow" if intent == "tomorrow" else "today"
    feels_text = f", feels up to {_format_temperature(apparent_max)}" if apparent_max is not None else ""
    answer = (
        f"{day_label.title()} in {location_name}: {_format_temperature(min_temp)} to "
        f"{_format_temperature(max_temp)}{feels_text}, {condition}, {precip_text}. "
        f"Open-Meteo forecast for {date_text}."
    )
    summary = f"open-meteo {day_label} forecast {location_name} {date_text}"
    return ToolResult(
        TOOL_STATUS_SUCCESS,
        summary,
        answer,
        {
            "category": ROUTE_WEATHER,
            "location": location_name,
            "source": "open-meteo",
            "intent": intent,
            "time": str(date_text),
            "freshness": f"forecast for {date_text}",
            "temperature_min_c": min_temp,
            "temperature_max_c": max_temp,
            "apparent_temperature_max_c": apparent_max if apparent_max is not None else "",
            "weather_code": weather_code if weather_code is not None else "",
            "precipitation_mm": precipitation if precipitation is not None else "",
            "rain_mm": rain if rain is not None else "",
            "precipitation_probability_max_percent": probability if probability is not None else "",
        },
    )


def _daily_value(daily: Mapping[str, Any], name: str, index: int, *, context: str) -> str | float:
    values = daily.get(name)
    if not isinstance(values, list) or len(values) <= index:
        raise ProviderError(PROVIDER_ERROR_MISSING_DATA, f"Open-Meteo {context} missing {name}")
    value = values[index]
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return value
    raise ProviderError(PROVIDER_ERROR_MISSING_DATA, f"Open-Meteo {context} malformed {name}")


def _fx_amount(route: ToolRoute) -> Decimal:
    raw_amount = str(route.params.get("amount") or "1").strip()
    try:
        amount = Decimal(raw_amount)
    except InvalidOperation as exc:
        raise ProviderError(PROVIDER_ERROR_INVALID_AMOUNT, f"FX amount is invalid: {raw_amount}") from exc
    if amount <= 0:
        raise ProviderError(PROVIDER_ERROR_INVALID_AMOUNT, "FX amount must be greater than zero")
    return amount


def _fx_pair(route: ToolRoute, provider_config: ProviderConfig) -> tuple[str, str, str]:
    configured_default = provider_config.default_base_currency.strip().upper() or DEFAULT_BASE_CURRENCY
    base = str(route.params.get("base") or "").strip().upper()
    quote = str(route.params.get("quote") or "").strip().upper()
    notes: list[str] = []
    if not base:
        base = configured_default
        notes.append(f"Defaulted base to {base}.")
    if not quote:
        if base != configured_default:
            quote = configured_default
        else:
            quote = DEFAULT_QUOTE_CURRENCY
        notes.append(f"Defaulted quote to {quote}.")
    return base, quote, " ".join(notes)


def _fx_number_field(values: Mapping[str, Any], name: str) -> float:
    value = values.get(name)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise ProviderError(PROVIDER_ERROR_MISSING_RATE_FIELDS, f"Frankfurter rate missing {name}")


def _fx_string_field(values: Mapping[str, Any], name: str) -> str:
    value = values.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ProviderError(PROVIDER_ERROR_MISSING_RATE_FIELDS, f"Frankfurter rate missing {name}")


def _daily_number(daily: Mapping[str, Any], name: str, index: int, *, context: str) -> float:
    value = _daily_value(daily, name, index, context=context)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise ProviderError(PROVIDER_ERROR_MISSING_DATA, f"Open-Meteo {context} malformed {name}")


def _optional_daily_number(daily: Mapping[str, Any], name: str, index: int) -> float | None:
    values = daily.get(name)
    if not isinstance(values, list) or len(values) <= index:
        return None
    value = values[index]
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _number_field(values: Mapping[str, Any], name: str, *, context: str) -> float:
    value = values.get(name)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise ProviderError(PROVIDER_ERROR_MISSING_DATA, f"{context} missing {name}")


def _optional_number_field(values: Mapping[str, Any], name: str) -> float | None:
    value = values.get(name)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _string_field(values: Mapping[str, Any], name: str, *, context: str) -> str:
    value = values.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ProviderError(PROVIDER_ERROR_MISSING_DATA, f"{context} missing {name}")


def _format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def _format_rate(value: float) -> str:
    return f"{value:.8g}"


def _format_temperature(value: float | None) -> str:
    if value is None:
        return "unknown temperature"
    return f"{value:.0f}C" if value.is_integer() else f"{value:.1f}C"


def _precipitation_text(
    *,
    precipitation: float | None,
    rain: float | None,
    probability: float | None,
) -> str:
    parts = []
    if probability is not None:
        parts.append(f"precipitation chance {probability:.0f}%")
    if precipitation is not None:
        parts.append(f"precipitation {precipitation:.1f} mm")
    if rain is not None:
        parts.append(f"rain {rain:.1f} mm")
    return ", ".join(parts) if parts else "precipitation not reported"


def _weather_code_label(weather_code: float | None) -> str:
    if weather_code is None:
        return "weather code not reported"
    code = int(weather_code)
    labels = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        80: "slight rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        95: "thunderstorm",
    }
    label = labels.get(code, "weather code")
    return f"{label} ({code})"

"""Deterministic structured-tool routing and tool execution."""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Mapping, MutableSequence


TOOL_STATUS_SUCCESS = "success"
TOOL_STATUS_NOT_CONFIGURED = "not_configured"
TOOL_STATUS_REFUSED = "refused"
TOOL_STATUS_NOOP = "noop"
TOOL_STATUS_ERROR = "error"

ROUTE_CALCULATOR = "calculator"
ROUTE_TIME = "time"
ROUTE_WEATHER = "weather"
ROUTE_STOCK = "stock"
ROUTE_FX = "fx"
ROUTE_UNSUPPORTED_REALTIME = "unsupported_realtime"
ROUTE_NONE = "none"

PLANNED_PROVIDER_TOOLS = {ROUTE_WEATHER, ROUTE_STOCK, ROUTE_FX}
NATURALIZABLE_PROVIDER_TOOLS = {ROUTE_WEATHER, ROUTE_STOCK, ROUTE_FX}


@dataclass(frozen=True)
class ToolRoute:
    """A deterministic route decision for one transcribed user request."""

    category: str
    tool_name: str
    params: Mapping[str, str] = field(default_factory=dict)
    reason: str = ""

    @property
    def uses_tool(self) -> bool:
        return self.category != ROUTE_NONE


@dataclass(frozen=True)
class ToolResult:
    """The structured result returned by a routed tool."""

    status: str
    summary: str
    answer: str
    data: Mapping[str, str | float] = field(default_factory=dict)

    @property
    def handled(self) -> bool:
        return self.status in {
            TOOL_STATUS_SUCCESS,
            TOOL_STATUS_NOT_CONFIGURED,
            TOOL_STATUS_REFUSED,
            TOOL_STATUS_ERROR,
        }


def route_text(text: str) -> ToolRoute:
    """Classify text into a deterministic route without model calls."""

    normalized = _normalize_text(text)
    if not normalized:
        return ToolRoute(ROUTE_NONE, "chat", reason="empty input")

    expression = _extract_calculator_expression(text)
    if expression is not None:
        return ToolRoute(
            ROUTE_CALCULATOR,
            "safe_calculator",
            {"expression": expression},
            "calculator expression detected",
        )

    if _contains_any(normalized, _TIME_MARKERS):
        return ToolRoute(ROUTE_TIME, "local_time", {"timezone": "local"}, "local time request")

    if _contains_any(normalized, _WEATHER_MARKERS):
        weather_params = _extract_weather_params(text)
        return ToolRoute(
            ROUTE_WEATHER,
            "weather_provider",
            weather_params,
            "weather request",
        )

    if _contains_any(normalized, _FX_MARKERS):
        fx_params = _extract_fx_params(text)
        return ToolRoute(
            ROUTE_FX,
            "fx_provider",
            fx_params,
            "foreign exchange request",
        )

    if _looks_like_stock_request(text):
        stock_params = _extract_stock_params(text)
        return ToolRoute(
            ROUTE_STOCK,
            "stock_provider",
            stock_params,
            "stock quote request",
        )

    if is_realtime_sensitive(text):
        return ToolRoute(
            ROUTE_UNSUPPORTED_REALTIME,
            "realtime_refusal",
            {"query": text.strip()},
            "unsupported realtime-sensitive request",
        )

    return ToolRoute(ROUTE_NONE, "chat", reason="no tool route matched")


def is_realtime_sensitive(text: str) -> bool:
    """Return true when a request needs fresh data but no local route matched."""

    normalized = _normalize_text(text)
    return _contains_any(normalized, _REALTIME_SENSITIVE_MARKERS)


def execute_route(
    route: ToolRoute,
    *,
    now_provider: Callable[[], datetime] | None = None,
    provider_config: object | None = None,
    http_client: object | None = None,
) -> ToolResult:
    """Execute a routed local tool or return a configured failure result."""

    if route.category == ROUTE_TIME:
        return _local_time_result(now_provider or _local_now)
    if route.category == ROUTE_CALCULATOR:
        expression = route.params.get("expression", "")
        return _calculator_result(expression)
    if route.category == ROUTE_WEATHER:
        return _weather_result(route, provider_config=provider_config, http_client=http_client)
    if route.category == ROUTE_FX:
        return _fx_result(route, provider_config=provider_config, http_client=http_client)
    if route.category == ROUTE_STOCK:
        return _stock_result(route, provider_config=provider_config, http_client=http_client)
    if route.category == ROUTE_UNSUPPORTED_REALTIME:
        return ToolResult(
            TOOL_STATUS_REFUSED,
            "unsupported realtime request",
            (
                "I cannot answer realtime news or live-data questions without a configured provider. "
                "Ask a non-realtime question or configure a provider-backed tool first."
            ),
            {"query": route.params.get("query", "")},
        )
    return ToolResult(TOOL_STATUS_NOOP, "no tool route", "", {})


def answer_with_tools(
    text: str,
    *,
    chat_client: object,
    history: MutableSequence[dict[str, str]],
    tools_enabled: bool,
    naturalize_tool_answers: bool = False,
    now_provider: Callable[[], datetime] | None = None,
    provider_config: object | None = None,
    http_client: object | None = None,
) -> tuple[str, ToolRoute, ToolResult | None]:
    """Answer text through tools when enabled, otherwise through chat."""

    route = route_text(text)
    if tools_enabled and route.uses_tool:
        result = execute_route(
            route,
            now_provider=now_provider,
            provider_config=provider_config,
            http_client=http_client,
        )
        if result.handled:
            answer = _naturalized_or_raw_answer(
                text,
                route,
                result,
                chat_client=chat_client,
                enabled=naturalize_tool_answers,
            )
            return answer, route, result

    answer = chat_client.ask_chatgpt(text, history)
    return answer, route, None


def format_text_debug(
    text: str,
    *,
    now_provider: Callable[[], datetime] | None = None,
    provider_config: object | None = None,
    http_client: object | None = None,
) -> str:
    """Format a dependency-free text debug report for CLI output."""

    route = route_text(text)
    result = (
        execute_route(
            route,
            now_provider=now_provider,
            provider_config=provider_config,
            http_client=http_client,
        )
        if route.uses_tool
        else None
    )
    final_answer = result.answer if result is not None and result.handled else "(would use chat)"
    raw_answer = result.answer if result is not None and result.handled else ""
    lines = [
        f"input={text}",
        f"route={route.category}",
        f"tool={route.tool_name}",
        f"params={_format_mapping(route.params)}",
        f"provider_config={_format_provider_config(provider_config)}",
        f"result_status={result.status if result is not None else 'not_run'}",
        f"result_summary={result.summary if result is not None else 'no tool route'}",
        f"raw_answer={raw_answer}",
        f"naturalization_status={_text_debug_naturalization_status(route, result)}",
        f"final_answer={final_answer}",
    ]
    return "\n".join(lines)


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _local_time_result(now_provider: Callable[[], datetime]) -> ToolResult:
    now = now_provider().astimezone()
    timezone_name = now.tzname() or "local time"
    clock = now.strftime("%H:%M")
    date_text = now.strftime("%Y-%m-%d")
    return ToolResult(
        TOOL_STATUS_SUCCESS,
        f"local time {date_text} {clock} {timezone_name}",
        f"The local time is {clock} on {date_text} ({timezone_name}).",
        {"date": date_text, "time": clock, "timezone": timezone_name},
    )


def _calculator_result(expression: str) -> ToolResult:
    try:
        value = _safe_eval_expression(expression)
    except ValueError as exc:
        return ToolResult(
            TOOL_STATUS_ERROR,
            "calculator error",
            f"I could not safely calculate that expression: {exc}",
            {"expression": expression},
        )
    answer_value = _format_number(value)
    return ToolResult(
        TOOL_STATUS_SUCCESS,
        f"{expression} = {answer_value}",
        f"The answer is {answer_value}.",
        {"expression": expression, "value": float(value)},
    )


def _not_configured_result(route: ToolRoute, *, provider_config: object | None = None) -> ToolResult:
    category_labels = {
        ROUTE_WEATHER: "weather",
        ROUTE_STOCK: "stock market",
        ROUTE_FX: "foreign exchange",
    }
    label = category_labels.get(route.category, route.category)
    provider_name = _provider_name(route, provider_config)
    data: dict[str, str | float] = {
        "category": route.category,
        "query": route.params.get("query", ""),
    }
    if provider_name:
        data["provider"] = provider_name

    if route.category == ROUTE_STOCK and _missing_finnhub_key(provider_config):
        return ToolResult(
            TOOL_STATUS_NOT_CONFIGURED,
            "stock market provider credentials are missing",
            "I cannot answer stock market questions yet because FINNHUB_API_KEY is missing.",
            data | {"credential": "FINNHUB_API_KEY"},
        )

    provider_phrase = f" {provider_name}" if provider_name else ""
    return ToolResult(
        TOOL_STATUS_NOT_CONFIGURED,
        f"{label} provider{provider_phrase} is not implemented",
        f"I cannot answer {label} questions yet because provider behavior is not implemented.",
        data,
    )


def _weather_result(
    route: ToolRoute,
    *,
    provider_config: object | None,
    http_client: object | None,
) -> ToolResult:
    provider_name = _provider_name(route, provider_config)
    if provider_name and provider_name.casefold() != "open-meteo":
        return _not_configured_result(route, provider_config=provider_config)

    from .providers import JsonHttpClient, ProviderConfig, ProviderError, open_meteo_weather_result, provider_error_result

    config = provider_config if provider_config is not None else ProviderConfig()
    client = http_client if http_client is not None else JsonHttpClient()
    try:
        return open_meteo_weather_result(route, provider_config=config, http_client=client)
    except ProviderError as exc:
        return provider_error_result(route, exc)


def _fx_result(
    route: ToolRoute,
    *,
    provider_config: object | None,
    http_client: object | None,
) -> ToolResult:
    provider_name = _provider_name(route, provider_config)
    if provider_name and provider_name.casefold() != "frankfurter":
        return _not_configured_result(route, provider_config=provider_config)

    from .providers import JsonHttpClient, ProviderConfig, ProviderError, frankfurter_fx_result, provider_error_result

    config = provider_config if provider_config is not None else ProviderConfig()
    client = http_client if http_client is not None else JsonHttpClient()
    try:
        return frankfurter_fx_result(route, provider_config=config, http_client=client)
    except ProviderError as exc:
        return provider_error_result(route, exc)


def _stock_result(
    route: ToolRoute,
    *,
    provider_config: object | None,
    http_client: object | None,
) -> ToolResult:
    provider_name = _provider_name(route, provider_config)
    if provider_name and provider_name.casefold() != "finnhub":
        return _not_configured_result(route, provider_config=provider_config)

    from .providers import JsonHttpClient, ProviderConfig, ProviderError, finnhub_stock_quote_result, provider_error_result

    config = provider_config if provider_config is not None else ProviderConfig()
    client = http_client if http_client is not None else JsonHttpClient()
    try:
        return finnhub_stock_quote_result(route, provider_config=config, http_client=client)
    except ProviderError as exc:
        return provider_error_result(route, exc)


def _safe_eval_expression(expression: str) -> float:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("invalid expression") from exc
    return float(_eval_node(tree.body))


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("only numbers are allowed")
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPERATORS:
        return _ALLOWED_UNARY_OPERATORS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINARY_OPERATORS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, (ast.Div, ast.Mod)) and right == 0:
            raise ValueError("division by zero")
        return _ALLOWED_BINARY_OPERATORS[type(node.op)](left, right)
    raise ValueError("only +, -, *, /, %, and parentheses are supported")


def _extract_calculator_expression(text: str) -> str | None:
    english_expression = _english_arithmetic_to_expression(text)
    if english_expression is not None:
        return english_expression

    compact = (
        text.strip()
        .replace("（", "(")
        .replace("）", ")")
        .replace("＋", "+")
        .replace("－", "-")
        .replace("×", "*")
        .replace("÷", "/")
    )
    compact = compact.replace("加", "+").replace("减", "-").replace("乘", "*").replace("除以", "/").replace("除", "/")
    match = re.search(r"[-+*/%().\d\s]{3,}", compact)
    if not match:
        return None
    expression = match.group(0).strip()
    if not re.search(r"\d", expression) or not re.search(r"[-+*/%]", expression):
        return None
    return expression


def _english_arithmetic_to_expression(text: str) -> str | None:
    normalized = _normalize_text(text)
    normalized = re.sub(r"^(what is|what's|calculate|compute|please calculate)\s+", "", normalized)
    words = [word for word in re.split(r"[^a-z0-9.]+", normalized) if word]
    if not words:
        return None

    tokens: list[str] = []
    saw_operator = False
    index = 0
    while index < len(words):
        word = words[index]
        if word in _NUMBER_WORDS:
            tokens.append(str(_NUMBER_WORDS[word]))
        elif re.fullmatch(r"\d+(?:\.\d+)?", word):
            tokens.append(word)
        elif word in {"plus", "add"}:
            tokens.append("+")
            saw_operator = True
        elif word in {"minus", "subtract"}:
            tokens.append("-")
            saw_operator = True
        elif word in {"times", "multiplied", "multiply"}:
            tokens.append("*")
            saw_operator = True
        elif word == "divided":
            if index + 1 < len(words) and words[index + 1] == "by":
                index += 1
            tokens.append("/")
            saw_operator = True
        elif word in {"over"}:
            tokens.append("/")
            saw_operator = True
        elif word in {"by", "and", "equals", "equal"}:
            pass
        else:
            return None
        index += 1

    if not saw_operator or not any(token.replace(".", "", 1).isdigit() for token in tokens):
        return None
    return " ".join(tokens)


def _normalize_text(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _looks_like_stock_request(text: str) -> bool:
    if _contains_any(_normalize_text(text), _STOCK_MARKERS):
        return True
    return _extract_stock_ticker(text) is not None


def _extract_weather_params(text: str) -> Mapping[str, str]:
    stripped = text.strip()
    normalized = _normalize_text(text)
    intent = "current"
    if _contains_any(normalized, _WEATHER_TOMORROW_MARKERS):
        intent = "tomorrow"
    elif _contains_any(normalized, _WEATHER_TODAY_MARKERS):
        intent = "today"

    location = _extract_weather_location(stripped, normalized)
    params = {"query": stripped, "intent": intent}
    if location:
        params["location"] = location
    return params


def _extract_weather_location(text: str, normalized: str) -> str:
    english_match = re.search(
        r"\b(?:in|for|at)\s+([a-z][a-z\s.'-]{1,80}?)(?:\s+(?:today|tomorrow|now|right now|weather|forecast|temperature|rain)|[?.!,]|$)",
        normalized,
    )
    if english_match:
        return _clean_weather_location(english_match.group(1))

    if re.search(r"[\u4e00-\u9fff]", text):
        location = text
        for marker in _WEATHER_CN_STOP_MARKERS:
            location = location.replace(marker, "")
        location = re.sub(r"[?？!！,，.。]", "", location)
        location = _clean_weather_location(location)
        if location and location not in {"怎么样", "如何", "多少", "几度", "會", "会"}:
            return location

    return ""


def _clean_weather_location(value: str) -> str:
    cleaned = _normalize_text(value)
    cleaned = re.sub(r"\b(what is|what's|how is|show me|tell me|please|the)\b", " ", cleaned)
    cleaned = re.sub(r"\b(weather|forecast|temperature|rain|raining|today|tomorrow|now|right now)\b", " ", cleaned)
    cleaned = " ".join(cleaned.split(" 的 "))
    return " ".join(cleaned.split()).strip(" ?!.，,。")


def _extract_fx_params(text: str) -> Mapping[str, str]:
    stripped = text.strip()
    params: dict[str, str] = {"query": stripped, "amount": _extract_fx_amount(stripped)}
    mentions = _find_currency_mentions(stripped)
    unsupported = _find_unsupported_currency_codes(stripped)
    if unsupported:
        params["unsupported_currency"] = unsupported[0]

    unique_mentions: list[_CurrencyMention] = []
    for mention in mentions:
        if not unique_mentions or unique_mentions[-1].code != mention.code or unique_mentions[-1].start != mention.start:
            unique_mentions.append(mention)

    if len(unique_mentions) >= 2:
        params["base"] = unique_mentions[0].code
        params["quote"] = unique_mentions[1].code
    elif len(unique_mentions) == 1:
        mention = unique_mentions[0]
        if _single_currency_is_base(stripped, mention):
            params["base"] = mention.code
        else:
            params["quote"] = mention.code
    return params


def _extract_stock_params(text: str) -> Mapping[str, str]:
    stripped = text.strip()
    params = {"query": stripped}
    symbol = _extract_stock_symbol(stripped)
    if symbol:
        params["symbol"] = symbol
    return params


def _extract_stock_symbol(text: str) -> str | None:
    ticker = _extract_stock_ticker(text)
    if ticker:
        return ticker

    normalized = _normalize_text(text)
    occupied: list[tuple[int, int]] = []
    for alias, symbol in _STOCK_ALIAS_PAIRS:
        start = 0
        while True:
            index = normalized.find(alias, start)
            if index < 0:
                break
            end = index + len(alias)
            if _alias_has_word_boundaries(normalized, index, end, alias) and not _overlaps(index, end, occupied):
                return symbol
            occupied.append((index, end))
            start = index + 1
    return None


def _extract_stock_ticker(text: str) -> str | None:
    ticker_match = re.search(r"\b[A-Z]{1,5}(?:\.[A-Z])?\b", text)
    if not ticker_match:
        return None
    ticker = ticker_match.group(0)
    if ticker in _STOCK_TICKER_STOPWORDS:
        return None
    return ticker


@dataclass(frozen=True)
class _CurrencyMention:
    code: str
    start: int
    end: int


def _find_currency_mentions(text: str) -> list[_CurrencyMention]:
    normalized = text.casefold()
    mentions: list[_CurrencyMention] = []
    occupied: list[tuple[int, int]] = []
    for alias, code in _FX_ALIASES:
        start = 0
        while True:
            index = normalized.find(alias, start)
            if index < 0:
                break
            end = index + len(alias)
            if _alias_has_word_boundaries(normalized, index, end, alias) and not _overlaps(index, end, occupied):
                mentions.append(_CurrencyMention(code, index, end))
                occupied.append((index, end))
            start = index + 1
    return sorted(mentions, key=lambda mention: (mention.start, -(mention.end - mention.start)))


def _alias_has_word_boundaries(text: str, start: int, end: int, alias: str) -> bool:
    if re.fullmatch(r"[a-z0-9 ]+", alias):
        before = text[start - 1] if start > 0 else " "
        after = text[end] if end < len(text) else " "
        if alias[0].isalnum() and before.isalnum():
            return False
        if alias[-1].isalnum() and after.isalnum():
            return False
    return True


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < existing_end and end > existing_start for existing_start, existing_end in ranges)


def _find_unsupported_currency_codes(text: str) -> list[str]:
    codes = [match.group(0).upper() for match in re.finditer(r"\b[A-Z]{3}\b", text)]
    normalized_codes = [match.group(0).upper() for match in re.finditer(r"\b[a-zA-Z]{3}\b", text.casefold())]
    for code in normalized_codes:
        if code in _FX_KNOWN_UNSUPPORTED_CODES and code not in codes:
            codes.append(code)
    return [code for code in codes if code not in FX_SUPPORTED_CURRENCIES]


def _extract_fx_amount(text: str) -> str:
    match = re.search(r"(?<![A-Za-z])(?:\$|€|£|¥)?\s*(\d[\d,]*(?:\.\d+)?)", text)
    if not match:
        return "1"
    return match.group(1).replace(",", "")


def _single_currency_is_base(text: str, mention: _CurrencyMention) -> bool:
    amount_match = re.search(r"(?<![A-Za-z])(?:\$|€|£|¥)?\s*\d[\d,]*(?:\.\d+)?", text)
    if amount_match and 0 <= mention.start - amount_match.end() <= 8:
        return True
    before = text[: mention.start].casefold()
    return bool(re.search(r"(convert|change|exchange|换|換|把)\s*$", before))


def _format_mapping(values: Mapping[str, str]) -> str:
    if not values:
        return "{}"
    return "{" + ",".join(f"{key}:{value}" for key, value in sorted(values.items())) + "}"


def _naturalized_or_raw_answer(
    text: str,
    route: ToolRoute,
    result: ToolResult,
    *,
    chat_client: object,
    enabled: bool,
) -> str:
    if not _should_naturalize_tool_answer(route, result, enabled=enabled):
        return result.answer

    naturalize = getattr(chat_client, "naturalize_tool_answer", None)
    if not callable(naturalize):
        return result.answer

    try:
        naturalized = naturalize(
            question=text,
            route=_route_metadata(route),
            raw_answer=result.answer,
            summary=result.summary,
            data=result.data,
        )
    except Exception as exc:
        from ..openai_client import OpenAIClientError

        if isinstance(exc, OpenAIClientError):
            return result.answer
        raise

    stripped = naturalized.strip()
    return stripped or result.answer


def _should_naturalize_tool_answer(route: ToolRoute, result: ToolResult, *, enabled: bool) -> bool:
    return enabled and route.category in NATURALIZABLE_PROVIDER_TOOLS and result.status == TOOL_STATUS_SUCCESS


def _route_metadata(route: ToolRoute) -> Mapping[str, object]:
    return {
        "category": route.category,
        "tool_name": route.tool_name,
        "params": dict(route.params),
        "reason": route.reason,
    }


def _text_debug_naturalization_status(route: ToolRoute, result: ToolResult | None) -> str:
    if result is None:
        return "not_applicable"
    if _should_naturalize_tool_answer(route, result, enabled=True):
        return "not_run_text_debug"
    return "not_applicable"


def _format_provider_config(provider_config: object | None) -> str:
    if provider_config is None:
        return "{}"
    public_summary = getattr(provider_config, "public_summary", None)
    if public_summary is not None:
        return _format_public_mapping(public_summary())
    return _format_public_mapping(
        {
            "weather_provider": getattr(provider_config, "weather_provider", ""),
            "fx_provider": getattr(provider_config, "fx_provider", ""),
            "stock_provider": getattr(provider_config, "stock_provider", ""),
            "http_timeout_seconds": getattr(provider_config, "http_timeout_seconds", ""),
            "default_location": getattr(provider_config, "default_location", ""),
            "default_base_currency": getattr(provider_config, "default_base_currency", ""),
            "finnhub_api_key": "configured" if getattr(provider_config, "finnhub_api_key", None) else "missing",
        }
    )


def _format_public_mapping(values: Mapping[str, object]) -> str:
    if not values:
        return "{}"
    return "{" + ",".join(f"{key}:{value}" for key, value in sorted(values.items())) + "}"


def _provider_name(route: ToolRoute, provider_config: object | None) -> str:
    if provider_config is None:
        return ""
    attr_by_route = {
        ROUTE_WEATHER: "weather_provider",
        ROUTE_STOCK: "stock_provider",
        ROUTE_FX: "fx_provider",
    }
    attr = attr_by_route.get(route.category)
    if attr is None:
        return ""
    return str(getattr(provider_config, attr, "")).strip()


def _missing_finnhub_key(provider_config: object | None) -> bool:
    if provider_config is None:
        return False
    stock_provider = str(getattr(provider_config, "stock_provider", "")).strip().lower()
    return stock_provider == "finnhub" and not getattr(provider_config, "finnhub_api_key", None)


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.10g}"


_ALLOWED_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
_ALLOWED_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_TIME_MARKERS = (
    "what time",
    "current time",
    "local time",
    "time is it",
    "现在几点",
    "几点",
    "時間",
    "时间",
)
_WEATHER_MARKERS = (
    "weather",
    "forecast",
    "temperature",
    "rain",
    "raining",
    "天气",
    "天氣",
    "温度",
    "下雨",
)
_WEATHER_TODAY_MARKERS = (
    "today",
    "tonight",
    "今天",
    "今日",
)
_WEATHER_TOMORROW_MARKERS = (
    "tomorrow",
    "明天",
    "明日",
)
_WEATHER_CN_STOP_MARKERS = (
    "天气怎么样",
    "天氣怎麼樣",
    "天气如何",
    "天氣如何",
    "天气",
    "天氣",
    "温度",
    "多少度",
    "几度",
    "幾度",
    "会不会下雨",
    "會不會下雨",
    "下雨吗",
    "下雨嗎",
    "下雨",
    "今天",
    "今日",
    "明天",
    "明日",
    "现在",
    "現在",
    "怎么样",
    "怎麼樣",
    "如何",
    "吗",
    "嗎",
)
_FX_MARKERS = (
    "exchange rate",
    "currency exchange",
    "fx",
    "foreign exchange",
    "usd",
    "sgd",
    "cny",
    "eur",
    "jpy",
    "hkd",
    "gbp",
    "aud",
    "dollar",
    "euro",
    "yen",
    "pound",
    "人民币",
    "人民幣",
    "美元",
    "美金",
    "新币",
    "新幣",
    "欧元",
    "歐元",
    "日元",
    "日圆",
    "日圓",
    "港币",
    "港幣",
    "英镑",
    "英鎊",
    "澳元",
    "澳币",
    "澳幣",
    "汇率",
    "匯率",
    "兑换",
    "兌換",
    "外汇",
    "外匯",
)
_STOCK_MARKERS = (
    "stock",
    "share price",
    "market price",
    "ticker",
    "股票",
    "股价",
    "股價",
    "美股",
)
_STOCK_TICKER_STOPWORDS = {
    "A",
    "I",
    "US",
    "USA",
    "USD",
    "ETF",
    "IPO",
    "CEO",
    "CFO",
    "AI",
}
_STOCK_ALIAS_PAIRS = (
    ("alphabet", "GOOGL"),
    ("google", "GOOGL"),
    ("microsoft", "MSFT"),
    ("nvidia", "NVDA"),
    ("tesla", "TSLA"),
    ("amazon", "AMZN"),
    ("apple", "AAPL"),
    ("meta", "META"),
    ("facebook", "META"),
    ("苹果", "AAPL"),
    ("蘋果", "AAPL"),
    ("特斯拉", "TSLA"),
    ("英伟达", "NVDA"),
    ("英偉達", "NVDA"),
    ("微软", "MSFT"),
    ("微軟", "MSFT"),
    ("谷歌", "GOOGL"),
    ("亚马逊", "AMZN"),
    ("亞馬遜", "AMZN"),
)
_UNSUPPORTED_REALTIME_MARKERS = (
    "news",
    "headline",
    "breaking",
    "current events",
    "今天有什么新闻",
    "今天有什麼新聞",
    "新闻",
    "新聞",
    "最新消息",
)
_REALTIME_SENSITIVE_MARKERS = _UNSUPPORTED_REALTIME_MARKERS + (
    "latest",
    "current",
    "today",
    "right now",
    "now",
    "price",
    "weather",
    "stock",
    "rate",
    "现在",
    "今天",
    "最新",
    "当前",
    "实时",
    "實時",
    "价格",
    "價格",
)

FX_SUPPORTED_CURRENCIES = ("USD", "SGD", "CNY", "EUR", "JPY", "HKD", "GBP", "AUD")
_FX_KNOWN_UNSUPPORTED_CODES = ("CAD", "CHF", "IDR", "INR", "KRW", "MYR", "NZD", "PHP", "THB", "TWD")
_FX_ALIAS_PAIRS = (
    ("singapore dollars", "SGD"),
    ("singapore dollar", "SGD"),
    ("australian dollars", "AUD"),
    ("australian dollar", "AUD"),
    ("hong kong dollars", "HKD"),
    ("hong kong dollar", "HKD"),
    ("british pounds", "GBP"),
    ("british pound", "GBP"),
    ("us dollars", "USD"),
    ("u.s. dollars", "USD"),
    ("u.s. dollar", "USD"),
    ("american dollars", "USD"),
    ("american dollar", "USD"),
    ("dollars", "USD"),
    ("dollar", "USD"),
    ("euros", "EUR"),
    ("euro", "EUR"),
    ("japanese yen", "JPY"),
    ("yen", "JPY"),
    ("pounds sterling", "GBP"),
    ("pound sterling", "GBP"),
    ("sterling", "GBP"),
    ("pounds", "GBP"),
    ("pound", "GBP"),
    ("aussie dollars", "AUD"),
    ("aussie dollar", "AUD"),
    ("usd", "USD"),
    ("sgd", "SGD"),
    ("cny", "CNY"),
    ("rmb", "CNY"),
    ("eur", "EUR"),
    ("jpy", "JPY"),
    ("hkd", "HKD"),
    ("gbp", "GBP"),
    ("aud", "AUD"),
    ("人民币", "CNY"),
    ("人民幣", "CNY"),
    ("美元", "USD"),
    ("美金", "USD"),
    ("新加坡元", "SGD"),
    ("新币", "SGD"),
    ("新幣", "SGD"),
    ("坡币", "SGD"),
    ("坡幣", "SGD"),
    ("欧元", "EUR"),
    ("歐元", "EUR"),
    ("日元", "JPY"),
    ("日圆", "JPY"),
    ("日圓", "JPY"),
    ("港币", "HKD"),
    ("港幣", "HKD"),
    ("英镑", "GBP"),
    ("英鎊", "GBP"),
    ("澳元", "AUD"),
    ("澳币", "AUD"),
    ("澳幣", "AUD"),
)
_FX_ALIASES = tuple(sorted(_FX_ALIAS_PAIRS, key=lambda item: len(item[0]), reverse=True))

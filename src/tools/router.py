"""Deterministic structured-tool routing.

This module intentionally avoids network calls. Provider-backed tools such as
weather, FX, and stock can be connected later behind the same route/result
schemas without changing the voice state machine.
"""

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
        return ToolRoute(
            ROUTE_WEATHER,
            "weather_provider",
            {"query": text.strip()},
            "weather request requires configured provider",
        )

    if _contains_any(normalized, _FX_MARKERS):
        return ToolRoute(
            ROUTE_FX,
            "fx_provider",
            {"query": text.strip()},
            "FX request requires configured provider",
        )

    if _looks_like_stock_request(normalized):
        return ToolRoute(
            ROUTE_STOCK,
            "stock_provider",
            {"query": text.strip()},
            "stock or market request requires configured provider",
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
) -> ToolResult:
    """Execute a routed local tool or return a configured failure result."""

    if route.category == ROUTE_TIME:
        return _local_time_result(now_provider or _local_now)
    if route.category == ROUTE_CALCULATOR:
        expression = route.params.get("expression", "")
        return _calculator_result(expression)
    if route.category in PLANNED_PROVIDER_TOOLS:
        return _not_configured_result(route)
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
    now_provider: Callable[[], datetime] | None = None,
) -> tuple[str, ToolRoute, ToolResult | None]:
    """Answer text through tools when enabled, otherwise through chat."""

    route = route_text(text)
    if tools_enabled and route.uses_tool:
        result = execute_route(route, now_provider=now_provider)
        if result.handled:
            return result.answer, route, result

    answer = chat_client.ask_chatgpt(text, history)
    return answer, route, None


def format_text_debug(text: str, *, now_provider: Callable[[], datetime] | None = None) -> str:
    """Format a dependency-free text debug report for CLI output."""

    route = route_text(text)
    result = execute_route(route, now_provider=now_provider) if route.uses_tool else None
    final_answer = result.answer if result is not None and result.handled else "(would use chat)"
    lines = [
        f"input={text}",
        f"route={route.category}",
        f"tool={route.tool_name}",
        f"params={_format_mapping(route.params)}",
        f"result_status={result.status if result is not None else 'not_run'}",
        f"result_summary={result.summary if result is not None else 'no tool route'}",
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


def _not_configured_result(route: ToolRoute) -> ToolResult:
    category_labels = {
        ROUTE_WEATHER: "weather",
        ROUTE_STOCK: "stock market",
        ROUTE_FX: "foreign exchange",
    }
    label = category_labels.get(route.category, route.category)
    return ToolResult(
        TOOL_STATUS_NOT_CONFIGURED,
        f"{label} provider is not configured",
        f"I cannot answer {label} questions yet because no provider is configured.",
        {"query": route.params.get("query", "")},
    )


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
    if _contains_any(text, _STOCK_MARKERS):
        return True
    return bool(re.search(r"\b(aapl|tsla|nvda|msft|googl?)\b", text))


def _format_mapping(values: Mapping[str, str]) -> str:
    if not values:
        return "{}"
    return "{" + ",".join(f"{key}:{value}" for key, value in sorted(values.items())) + "}"


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
    "天气",
    "天氣",
    "温度",
)
_FX_MARKERS = (
    "exchange rate",
    "fx",
    "foreign exchange",
    "usd",
    "eur",
    "美元",
    "欧元",
    "歐元",
    "汇率",
    "匯率",
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

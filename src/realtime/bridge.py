"""Deterministic loopback bridge boundary for the future Realtime controller."""

from __future__ import annotations

import json
import re
import time
from collections import deque
from typing import Callable, Mapping

from .contracts import HostCommand, HostCommandType, HostEvent, HostEventType, RealtimeLifecycle


MAX_BRIDGE_BYTES = 4096
MAX_BRIDGE_ITEMS = 16
MAX_BRIDGE_STRING = 1024
MAX_BRIDGE_DEPTH = 4
SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
FORBIDDEN_KEY_PARTS = ("api_key", "authorization", "secret", "token", "pcm", "audio_bytes", "audio_data")


class BridgeError(ValueError):
    """A bounded validation or lifecycle failure."""


class LoopbackBridge:
    """Queue typed host commands and accept events for exactly one session."""

    def __init__(self, host: str = "127.0.0.1", *, clock: Callable[[], float] = time.monotonic) -> None:
        if host not in LOOPBACK_HOSTS:
            raise BridgeError("Realtime bridge must bind to loopback")
        self.host = host
        self._clock = clock
        self.lifecycle = RealtimeLifecycle.WAIT_WAKE
        self.host_ready = False
        self.active_session_id: str | None = None
        self._next_command_id = 1
        self._commands: deque[HostCommand] = deque(maxlen=32)
        self._events: deque[HostEvent] = deque(maxlen=128)

    @property
    def commands(self) -> tuple[HostCommand, ...]:
        return tuple(self._commands)

    @property
    def events(self) -> tuple[HostEvent, ...]:
        return tuple(self._events)

    def start(self, session_id: str, detail: Mapping[str, object] | None = None) -> HostCommand:
        self._validate_session_id(session_id)
        if not self.host_ready:
            raise BridgeError("Realtime host is not ready")
        if self.active_session_id is not None or self.lifecycle is not RealtimeLifecycle.WAIT_WAKE:
            raise BridgeError("A Realtime session is already active")
        command = self._command(HostCommandType.START, session_id, detail or {})
        self.active_session_id = session_id
        self.lifecycle = RealtimeLifecycle.CONNECTING
        return command

    def close(self, session_id: str, detail: Mapping[str, object] | None = None) -> HostCommand:
        self._require_active(session_id)
        if self.lifecycle is RealtimeLifecycle.CLOSING:
            raise BridgeError("Realtime session is already closing")
        command = self._command(HostCommandType.CLOSE, session_id, detail or {})
        self.lifecycle = RealtimeLifecycle.CLOSING
        return command

    def shutdown(self) -> HostCommand:
        command = self._command(HostCommandType.SHUTDOWN, self.active_session_id, {})
        if self.active_session_id is not None:
            self.lifecycle = RealtimeLifecycle.CLOSING
        return command

    def receive(
        self,
        event_type: HostEventType | str,
        session_id: str | None,
        detail: Mapping[str, object] | None = None,
    ) -> HostEvent:
        try:
            resolved_type = HostEventType(event_type)
        except ValueError as exc:
            raise BridgeError("Unknown Realtime host event") from exc
        if resolved_type is HostEventType.READY:
            if session_id is not None or self.lifecycle is not RealtimeLifecycle.WAIT_WAKE:
                raise BridgeError("ready event was out of order or session-bound")
            safe_detail = _validate_detail(detail or {})
            event = HostEvent(resolved_type, None, self._clock(), safe_detail)
            self._events.append(event)
            self.host_ready = True
            return event
        if session_id is None:
            raise BridgeError("Realtime session identity is malformed")
        self._require_active(session_id)
        if resolved_type is HostEventType.CONNECTED:
            if self.lifecycle is not RealtimeLifecycle.CONNECTING:
                raise BridgeError(f"{resolved_type.value} event was out of order")
        elif resolved_type in {
            HostEventType.VAD,
            HostEventType.RESPONSE,
            HostEventType.TRANSCRIPTION,
            HostEventType.TOOL_CALL,
        } and self.lifecycle is not RealtimeLifecycle.ACTIVE_SESSION:
            raise BridgeError(f"{resolved_type.value} event requires an active session")
        safe_detail = _validate_detail(detail or {})
        event = HostEvent(resolved_type, session_id, self._clock(), safe_detail)
        self._events.append(event)
        if resolved_type is HostEventType.CONNECTED:
            self.lifecycle = RealtimeLifecycle.ACTIVE_SESSION
        elif resolved_type in {HostEventType.ERROR, HostEventType.CLOSED}:
            self.lifecycle = RealtimeLifecycle.WAIT_WAKE
            self.active_session_id = None
        return event

    def command_after(self, command_id: int) -> HostCommand | None:
        if not isinstance(command_id, int) or command_id < 0:
            raise BridgeError("Command cursor must be a non-negative integer")
        return next((command for command in self._commands if command.command_id > command_id), None)

    def _command(
        self,
        command_type: HostCommandType,
        session_id: str | None,
        detail: Mapping[str, object],
    ) -> HostCommand:
        safe_detail = _validate_detail(detail)
        command = HostCommand(self._next_command_id, command_type, session_id, self._clock(), safe_detail)
        _validate_wire_size(
            {
                "command_id": command.command_id,
                "type": command.type.value,
                "session_id": command.session_id,
                "detail": safe_detail,
            }
        )
        self._next_command_id += 1
        self._commands.append(command)
        return command

    def _require_active(self, session_id: str) -> None:
        self._validate_session_id(session_id)
        if session_id != self.active_session_id:
            raise BridgeError("Realtime event or command has a stale session identity")

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        if (
            not isinstance(session_id, str)
            or not SAFE_SESSION_ID.fullmatch(session_id)
            or session_id.lower().startswith("sk-")
        ):
            raise BridgeError("Realtime session identity is malformed")


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("Fake clock cannot move backwards")
        self.now += seconds


class FakeRealtimeHost:
    """Offline host fixture that emits deterministic lifecycle events."""

    def __init__(self, bridge: LoopbackBridge) -> None:
        self.bridge = bridge

    def ready(self) -> None:
        self.bridge.receive(HostEventType.READY, None)

    def connect(self, session_id: str) -> None:
        self.bridge.receive(HostEventType.CONNECTED, session_id)

    def close(self, session_id: str) -> None:
        self.bridge.receive(HostEventType.CLOSED, session_id, {"reason": "fake_host"})


def _validate_detail(detail: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(detail, Mapping):
        raise BridgeError("Realtime bridge detail must be an object")
    result = dict(detail)
    _validate_value(result, depth=0)
    _validate_wire_size(result)
    return result


def _validate_value(value: object, *, depth: int) -> None:
    if depth > MAX_BRIDGE_DEPTH:
        raise BridgeError("Realtime bridge payload is too deeply nested")
    if isinstance(value, Mapping):
        if len(value) > MAX_BRIDGE_ITEMS:
            raise BridgeError("Realtime bridge payload has too many fields")
        for key, nested in value.items():
            if not isinstance(key, str) or len(key) > 100:
                raise BridgeError("Realtime bridge payload key is malformed")
            lowered = key.lower()
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                raise BridgeError("Realtime bridge payload contains forbidden audio or secret material")
            _validate_value(nested, depth=depth + 1)
        return
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_BRIDGE_ITEMS:
            raise BridgeError("Realtime bridge payload has too many items")
        for nested in value:
            _validate_value(nested, depth=depth + 1)
        return
    if isinstance(value, str):
        if len(value) > MAX_BRIDGE_STRING or value.startswith("sk-") or value.lower().startswith("bearer "):
            raise BridgeError("Realtime bridge payload contains an oversized or secret-bearing value")
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        raise BridgeError("Realtime bridge payload contains a non-JSON value")


def _validate_wire_size(payload: Mapping[str, object]) -> None:
    try:
        size = len(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    except (TypeError, ValueError) as exc:
        raise BridgeError("Realtime bridge payload is not JSON-safe") from exc
    if size > MAX_BRIDGE_BYTES:
        raise BridgeError("Realtime bridge payload exceeds the bounded size")

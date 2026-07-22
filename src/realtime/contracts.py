"""Typed, PCM-free lifecycle messages shared by Python and the WebRTC host."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class RealtimeLifecycle(str, Enum):
    WAIT_WAKE = "WAIT_WAKE"
    CONNECTING = "CONNECTING"
    ACTIVE_SESSION = "ACTIVE_SESSION"
    CLOSING = "CLOSING"


class HostCommandType(str, Enum):
    START = "start"
    CLOSE = "close"
    SHUTDOWN = "shutdown"


class HostEventType(str, Enum):
    READY = "ready"
    CONNECTED = "connected"
    VAD = "vad"
    RESPONSE = "response"
    TRANSCRIPTION = "transcription"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    CLOSED = "closed"


@dataclass(frozen=True)
class HostCommand:
    command_id: int
    type: HostCommandType
    session_id: str | None
    at_seconds: float
    detail: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class HostEvent:
    type: HostEventType
    session_id: str | None
    at_seconds: float
    detail: Mapping[str, object] = field(default_factory=dict)

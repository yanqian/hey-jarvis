"""Exclusive microphone handoff coordination for a browser WebRTC host."""

from __future__ import annotations

import re
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol


MAX_EVIDENCE_EVENTS = 200
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
MAX_TRANSCRIPT_CONTROL_CHARS = 200
MAX_NORMALIZED_END_PHRASE_CHARS = 64


class HandoffError(RuntimeError):
    """A bounded operator-facing handoff error."""


class MicrophoneLease(Protocol):
    @property
    def is_open(self) -> bool: ...

    def open(self) -> None: ...

    def close(self) -> None: ...


class HandoffState(str, Enum):
    WAKE_OWNED = "wake_owned"
    HOST_STARTING = "host_starting"
    HOST_ACTIVE = "host_active"
    HOST_STOPPING = "host_stopping"


@dataclass(frozen=True)
class HostCommand:
    command_id: int
    type: str
    session_id: str

    def as_dict(self) -> dict[str, object]:
        return {"command_id": self.command_id, "type": self.type, "session_id": self.session_id}


class SoundDeviceWakeLease:
    """Own the existing input stream only while local wake listening is active."""

    def __init__(self, stream_factory: Callable[[], object]) -> None:
        self._stream_factory = stream_factory
        self._stream: object | None = None

    @property
    def is_open(self) -> bool:
        return self._stream is not None

    def open(self) -> None:
        if self._stream is None:
            self._stream = self._stream_factory()

    def close(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            close = getattr(stream, "close", None)
            if close is not None:
                close()

    def read_chunk(self) -> bytes:
        if self._stream is None:
            raise HandoffError("Wake microphone is not open")
        read_chunk = getattr(self._stream, "read_chunk", None)
        if read_chunk is None:
            raise HandoffError("Wake microphone stream cannot provide chunks")
        return bytes(read_chunk())


class HandoffCoordinator:
    """Serialize wake-stream and WebRTC-host microphone ownership."""

    def __init__(
        self,
        wake_lease: MicrophoneLease,
        *,
        clock: Callable[[], float] = time.monotonic,
        session_ids: Callable[[], str] = lambda: uuid.uuid4().hex,
        open_wake_on_init: bool = True,
        end_phrases: tuple[str, ...] = (),
    ) -> None:
        self._wake_lease = wake_lease
        self._clock = clock
        self._session_ids = session_ids
        self._lock = threading.RLock()
        self._armed = False
        self._host_id: str | None = None
        self._state = HandoffState.WAKE_OWNED
        self._session_id: str | None = None
        self._transport_connected = False
        self._session_created = False
        self._session_configured = False
        self._connected_at: float | None = None
        self._last_activity_at: float | None = None
        self._next_command_id = 1
        self._commands: list[HostCommand] = []
        self._evidence: list[dict[str, object]] = []
        self._end_phrases = frozenset(
            normalized
            for normalized in (_normalize_end_phrase(value) for value in end_phrases)
            if normalized and len(normalized) <= MAX_NORMALIZED_END_PHRASE_CHARS
        )
        self._seen_transcription_items: set[str] = set()
        if open_wake_on_init:
            if not self._wake_lease.is_open:
                self._wake_lease.open()
            self._record("wake_microphone_opened")
        else:
            self._record("wake_microphone_deferred_until_arm")

    @property
    def state(self) -> HandoffState:
        return self._state

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def wake_microphone_open(self) -> bool:
        return self._wake_lease.is_open

    def read_wake_chunk(self) -> bytes:
        with self._lock:
            if self._state != HandoffState.WAKE_OWNED:
                raise HandoffError("Wake microphone cannot be read during a host session")
            read_chunk = getattr(self._wake_lease, "read_chunk", None)
            if read_chunk is None:
                raise HandoffError("Wake microphone lease cannot provide chunks")
            return bytes(read_chunk())

    def release_wake_for_acknowledgement(self) -> None:
        with self._lock:
            if self._state != HandoffState.WAKE_OWNED:
                raise HandoffError("Wake microphone can only be released from WAIT_WAKE")
            if self._wake_lease.is_open:
                self._wake_lease.close()
                self._record("wake_microphone_closed", reason="pre_capture_acknowledgement")

    def restore_wake_microphone(self, reason: str) -> None:
        with self._lock:
            if self._state == HandoffState.WAKE_OWNED and self._session_id is None and not self._wake_lease.is_open:
                self._wake_lease.open()
                self._record("wake_microphone_reopened", result=reason)

    def arm_host(self, host_id: str | None = None) -> None:
        with self._lock:
            if host_id is not None and not _SAFE_VALUE.fullmatch(host_id):
                raise HandoffError("Host identity was invalid")
            if self._session_id is not None and host_id != self._host_id:
                raise HandoffError("A different host already owns the active session")
            self._host_id = host_id
            if self._state == HandoffState.WAKE_OWNED and not self._wake_lease.is_open:
                self._wake_lease.open()
                self._record("wake_microphone_opened", reason="host_armed")
            self._armed = True
            self._record("host_armed")

    def begin_handoff(self) -> str:
        with self._lock:
            if not self._armed:
                raise HandoffError("WebRTC host must be armed once before wake handoff")
            if self._state != HandoffState.WAKE_OWNED:
                raise HandoffError("A microphone handoff is already active")
            session_id = self._session_ids()
            if not _SAFE_VALUE.fullmatch(session_id):
                raise HandoffError("Session identity was invalid")
            if self._wake_lease.is_open:
                self._wake_lease.close()
                self._record("wake_microphone_closed", reason="handoff")
            self._session_id = session_id
            self._transport_connected = False
            self._session_created = False
            self._session_configured = False
            self._connected_at = None
            self._last_activity_at = self._clock()
            self._seen_transcription_items.clear()
            self._state = HandoffState.HOST_STARTING
            self._enqueue("start", session_id)
            return session_id

    def request_stop(self, reason: str = "requested") -> None:
        with self._lock:
            if self._session_id is None or self._state == HandoffState.WAKE_OWNED:
                return
            if self._state != HandoffState.HOST_STOPPING:
                self._state = HandoffState.HOST_STOPPING
                self._enqueue("stop", self._session_id, reason=reason)

    def timeout_reason(self, *, idle_seconds: float, max_duration_seconds: float) -> str | None:
        with self._lock:
            if self._state != HandoffState.HOST_ACTIVE or self._connected_at is None:
                return None
            now = self._clock()
            if now - self._connected_at >= max_duration_seconds:
                return "max_duration"
            if self._last_activity_at is not None and now - self._last_activity_at >= idle_seconds:
                return "idle_timeout"
            return None

    def request_long_answer(self) -> None:
        with self._lock:
            if self._session_id is None or self._state != HandoffState.HOST_ACTIVE:
                raise HandoffError("A connected host session is required")
            self._enqueue("long_answer", self._session_id)

    def host_event(
        self,
        event_type: str,
        session_id: str | None = None,
        *,
        host_id: str | None = None,
        **detail: object,
    ) -> str:
        with self._lock:
            if event_type == "armed":
                self.arm_host(host_id)
                return "accepted"
            if not _SAFE_VALUE.fullmatch(event_type):
                raise HandoffError("Host event type was invalid")
            if host_id != self._host_id:
                raise HandoffError("Host event did not match the armed host")
            if session_id != self._session_id or self._session_id is None:
                raise HandoffError("Host event did not match the active session")
            if event_type in {"microphone_requested", "microphone_acquired"} and self._wake_lease.is_open:
                raise HandoffError("Host microphone requested before wake microphone closed")
            if event_type == "transcription":
                return self._handle_completed_transcription(session_id, detail)
            if event_type == "transcription_failed":
                self._record("host_transcription_failed", session_id=session_id, reason="provider_failure")
                self._last_activity_at = self._clock()
                return "accepted"
            safe_detail = {
                key: value
                for key, value in detail.items()
                if key in {"echoCancellation", "noiseSuppression", "autoGainControl", "sampleRate", "channelCount", "reason"}
                and isinstance(value, (str, int, float, bool))
            }
            self._record(f"host_{event_type}", session_id=session_id, **safe_detail)
            if event_type == "connected":
                self._transport_connected = True
                self._session_created = True
                self._session_configured = True
            elif event_type == "transport_connected":
                self._transport_connected = True
            elif event_type == "session_created":
                self._session_created = True
            if (
                self._transport_connected
                and self._session_created
                and self._session_configured
                and event_type == "connected"
            ):
                self._state = HandoffState.HOST_ACTIVE
                self._connected_at = self._clock()
                self._last_activity_at = self._connected_at
            if event_type in {"speech_started", "speech_stopped", "response_created", "response_done", "transcription"}:
                self._last_activity_at = self._clock()
            if event_type == "error":
                self.request_stop(str(safe_detail.get("reason", "host_error")))
            elif event_type == "stopped":
                self._finish_handoff(event_type)
            return "stopping" if self._state == HandoffState.HOST_STOPPING else "accepted"

    def _handle_completed_transcription(self, session_id: str, detail: dict[str, object]) -> str:
        item_id = detail.get("item_id")
        if not isinstance(item_id, str) or not _SAFE_VALUE.fullmatch(item_id):
            self._record("host_transcription_ignored", session_id=session_id, reason="missing_item")
            return "accepted"
        if self._state != HandoffState.HOST_ACTIVE:
            self._record("host_transcription_ignored", session_id=session_id, reason="late_event")
            return "stopping" if self._state == HandoffState.HOST_STOPPING else "accepted"
        if item_id in self._seen_transcription_items:
            self._record("host_transcription_duplicate", session_id=session_id)
            return "accepted"
        self._seen_transcription_items.add(item_id)
        transcript = detail.get("transcript")
        if not isinstance(transcript, str) or not transcript.strip():
            self._record("host_transcription_ignored", session_id=session_id, reason="missing_text")
            return "accepted"
        if len(transcript) > MAX_TRANSCRIPT_CONTROL_CHARS:
            self._record("host_transcription_ignored", session_id=session_id, reason="too_long")
            return "accepted"
        self._record("host_transcription", session_id=session_id)
        self._last_activity_at = self._clock()
        normalized = _normalize_end_phrase(transcript)
        if len(normalized) > MAX_NORMALIZED_END_PHRASE_CHARS:
            self._record("host_transcription_ignored", session_id=session_id, reason="not_short")
            return "accepted"
        if normalized and normalized in self._end_phrases:
            self._record("host_end_phrase_matched", session_id=session_id)
            self.request_stop("end_phrase")
            return "stopping"
        return "accepted"

    def command_after(self, command_id: int, *, host_id: str | None = None) -> dict[str, object] | None:
        with self._lock:
            if host_id != self._host_id:
                return None
            return next((command.as_dict() for command in self._commands if command.command_id > command_id), None)

    def report(self) -> dict[str, object]:
        with self._lock:
            return {
                "host": "chrome-app-mode",
                "initial_arming": "once per host launch",
                "state": self._state.value,
                "wake_microphone_open": self._wake_lease.is_open,
                "active_session": self._session_id is not None,
                "events": list(self._evidence),
            }

    def close(self) -> None:
        with self._lock:
            self.request_stop()
            self._wake_lease.close()
            self._record("coordinator_closed")

    def _finish_handoff(self, result: str) -> None:
        session_id = self._session_id
        self._session_id = None
        self._transport_connected = False
        self._session_created = False
        self._session_configured = False
        self._connected_at = None
        self._last_activity_at = None
        self._seen_transcription_items.clear()
        if not self._wake_lease.is_open:
            self._wake_lease.open()
        self._state = HandoffState.WAKE_OWNED
        self._record("wake_microphone_reopened", session_id=session_id, result=result)

    def _enqueue(self, command_type: str, session_id: str, **detail: object) -> None:
        command = HostCommand(self._next_command_id, command_type, session_id)
        self._next_command_id += 1
        self._commands.append(command)
        self._commands = self._commands[-32:]
        self._record("host_command", command=command_type, session_id=session_id, **detail)

    def _record(self, event_type: str, **detail: object) -> None:
        entry = {"at_ms": round(self._clock() * 1000), "type": event_type, **detail}
        self._evidence.append(entry)
        self._evidence = self._evidence[-MAX_EVIDENCE_EVENTS:]


def _normalize_end_phrase(value: str) -> str:
    """Normalize one complete short utterance without enabling substring matches."""

    text = unicodedata.normalize("NFKC", value).casefold().strip()
    while text and (text[0].isspace() or unicodedata.category(text[0]).startswith("P")):
        text = text[1:]
    while text and (text[-1].isspace() or unicodedata.category(text[-1]).startswith("P")):
        text = text[:-1]
    # Completed input transcription is only a rough guide and may insert spaces
    # inside a short spoken control phrase (for example ``good bye`` or
    # ``结束 对话``). Whitespace is not semantically significant for these
    # exact, whole-utterance controls; removing it does not enable substring
    # matching because the complete normalized value is still compared.
    return "".join(text.split())

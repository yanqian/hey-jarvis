"""Exclusive microphone handoff coordination for a browser WebRTC host."""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from src.tools import ToolRoute, execute_route


MAX_EVIDENCE_EVENTS = 200
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
MAX_TRANSCRIPT_CONTROL_CHARS = 200
MAX_NORMALIZED_END_PHRASE_CHARS = 64
MAX_TOOL_ARGUMENT_CHARS = 512
MAX_CALCULATOR_EXPRESSION_CHARS = 200
MAX_INPUT_LEVEL_SAMPLE_COUNT = 10
MAX_FIXTURE_AUDIO_BYTES = 384_000
MAX_HANDOFF_TIMING_MS = 60_000
FIXTURE_AUDIO_NAMES = frozenset({"turn-1", "turn-2"})
INPUT_LEVEL_PHASES = frozenset({"no_remote_playback", "remote_playback"})
LOCAL_TIMING_MARKERS = frozenset({"wake_confirmed", "ack_started", "ack_completed"})
HANDOFF_PHASE_TIMING_FIELDS = frozenset(
    {
        "command_to_token_ms",
        "token_ms",
        "microphone_ms",
        "peer_setup_ms",
        "negotiation_ms",
        "session_configuration_ms",
    }
)
PEER_SETUP_TIMING_FIELDS = frozenset(
    {
        "microphone_reporting_ms",
        "audio_analysis_setup_ms",
        "peer_connection_setup_ms",
        "offer_creation_ms",
        "local_description_ms",
    }
)
HANDOFF_TIMING_FIELDS = frozenset(
    {
        *HANDOFF_PHASE_TIMING_FIELDS,
        *PEER_SETUP_TIMING_FIELDS,
        "total_browser_ready_ms",
    }
)
NEGOTIATION_DIAGNOSTIC_FIELDS = frozenset(
    {
        "errorType",
        "errorCode",
        "requestId",
        "retryAfter",
        "rateLimitRemainingRequests",
        "rateLimitRemainingTokens",
        "rateLimitRemainingProjectTokens",
        "rateLimitResetRequests",
        "rateLimitResetTokens",
        "rateLimitResetProjectTokens",
    }
)


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
    detail: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        value = {"command_id": self.command_id, "type": self.type, "session_id": self.session_id}
        if self.detail:
            value.update(self.detail)
        return value


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
        self._handoff_timing_received = False
        self._next_command_id = 1
        self._commands: list[HostCommand] = []
        self._evidence: list[dict[str, object]] = []
        self._end_phrases = frozenset(
            normalized
            for normalized in (_normalize_end_phrase(value) for value in end_phrases)
            if normalized and len(normalized) <= MAX_NORMALIZED_END_PHRASE_CHARS
        )
        self._seen_transcription_items: set[str] = set()
        self._handled_tool_calls: set[str] = set()
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

    def record_local_timing_marker(self, marker: str) -> None:
        """Record one privacy-safe local wake/ack boundary."""

        with self._lock:
            if marker not in LOCAL_TIMING_MARKERS:
                raise HandoffError("Local timing marker was invalid")
            self._record(marker)

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
            self._handoff_timing_received = False
            self._seen_transcription_items.clear()
            self._handled_tool_calls.clear()
            self._state = HandoffState.HOST_STARTING
            self._record("handoff_queued", session_id=session_id)
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

    def request_fixture_audio(self, name: str, audio: str) -> None:
        """Queue private eval audio without retaining it in lifecycle evidence."""

        with self._lock:
            if self._session_id is None or self._state != HandoffState.HOST_ACTIVE:
                raise HandoffError("A connected host session is required")
            if name not in FIXTURE_AUDIO_NAMES:
                raise HandoffError("Fixture audio name was invalid")
            if not isinstance(audio, str) or not audio or len(audio) > MAX_FIXTURE_AUDIO_BYTES * 2:
                raise HandoffError("Fixture audio payload size was invalid")
            try:
                decoded = base64.b64decode(audio, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise HandoffError("Fixture audio payload was invalid") from exc
            if not decoded or len(decoded) > MAX_FIXTURE_AUDIO_BYTES or len(decoded) % 2:
                raise HandoffError("Fixture audio payload size was invalid")
            self._enqueue("fixture_audio", self._session_id, fixture_name=name, audio=audio)

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
            if event_type == "tool_call":
                return self._handle_tool_call(session_id, detail)
            if event_type == "input_level":
                safe_detail = _sanitize_input_level(detail)
            elif event_type == "handoff_timing":
                if self._handoff_timing_received:
                    raise HandoffError("Handoff timing was already reported")
                safe_detail = _sanitize_handoff_timing(detail)
                self._handoff_timing_received = True
            elif event_type == "error" and detail.get("reason") == "webrtc_negotiation_failed":
                safe_detail = _sanitize_negotiation_error(detail)
            else:
                safe_detail = {
                    key: value
                    for key, value in detail.items()
                    if key in {"echoCancellation", "noiseSuppression", "autoGainControl", "sampleRate", "channelCount", "outputVolume", "reason"}
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
            if event_type in {
                "fixture_submitted",
                "speech_started",
                "speech_stopped",
                "response_created",
                "response_done",
                "transcription",
            }:
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

    def _handle_tool_call(self, session_id: str, detail: dict[str, object]) -> str:
        call_id = detail.get("call_id")
        name = detail.get("name")
        arguments = detail.get("arguments")
        if not isinstance(call_id, str) or not _SAFE_VALUE.fullmatch(call_id):
            raise HandoffError("Realtime tool call identity was invalid")
        if call_id in self._handled_tool_calls:
            self._record("host_tool_call_duplicate", session_id=session_id)
            return "stopping" if self._state == HandoffState.HOST_STOPPING else "accepted"
        self._handled_tool_calls.add(call_id)
        if name == "end_conversation":
            if self._state != HandoffState.HOST_ACTIVE:
                self._record(
                    "host_end_conversation_tool_ignored",
                    session_id=session_id,
                    reason="late_event",
                )
                return "stopping" if self._state == HandoffState.HOST_STOPPING else "accepted"
            try:
                payload = (
                    json.loads(arguments)
                    if isinstance(arguments, str)
                    and len(arguments) <= MAX_TOOL_ARGUMENT_CHARS
                    else None
                )
            except json.JSONDecodeError:
                payload = None
            if payload != {}:
                self._record(
                    "host_end_conversation_tool_ignored",
                    session_id=session_id,
                    reason="invalid_arguments",
                )
                return "accepted"
            self._record("host_end_conversation_tool", session_id=session_id)
            self._last_activity_at = self._clock()
            self.request_stop("end_phrase")
            return "stopping"
        output = _calculator_output(name, arguments)
        self._enqueue("tool_result", session_id, call_id=call_id, output=output)
        self._record("host_tool_call", session_id=session_id, result="completed")
        self._last_activity_at = self._clock()
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
        self._handoff_timing_received = False
        self._seen_transcription_items.clear()
        self._handled_tool_calls.clear()
        if not self._wake_lease.is_open:
            self._wake_lease.open()
        self._state = HandoffState.WAKE_OWNED
        self._record("wake_microphone_reopened", session_id=session_id, result=result)

    def _enqueue(self, command_type: str, session_id: str, **detail: object) -> None:
        command = HostCommand(self._next_command_id, command_type, session_id, dict(detail) or None)
        self._next_command_id += 1
        self._commands.append(command)
        self._commands = self._commands[-32:]
        # The browser still receives command detail, but the default report only
        # records lifecycle metadata. In particular, tool call ids and outputs
        # must never become durable diagnostic evidence.
        evidence_detail = {"reason": detail["reason"]} if "reason" in detail else {}
        self._record("host_command", command=command_type, session_id=session_id, **evidence_detail)

    def _record(self, event_type: str, **detail: object) -> None:
        safe_detail = {
            key: value if not isinstance(value, str) or _SAFE_VALUE.fullmatch(value) else "[redacted]"
            for key, value in detail.items()
        }
        entry = {"at_ms": round(self._clock() * 1000), "type": event_type, **safe_detail}
        self._evidence.append(entry)
        self._evidence = self._evidence[-MAX_EVIDENCE_EVENTS:]


def _sanitize_handoff_timing(detail: dict[str, object]) -> dict[str, int]:
    if set(detail) != HANDOFF_TIMING_FIELDS:
        raise HandoffError("Handoff timing fields were incomplete or unsupported")
    safe: dict[str, int] = {}
    for field in HANDOFF_TIMING_FIELDS:
        value = detail.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise HandoffError("Handoff timing values must be integer milliseconds")
        if value < 0 or value > MAX_HANDOFF_TIMING_MS:
            raise HandoffError("Handoff timing value was outside the allowed range")
        safe[field] = value
    phase_total = sum(safe[field] for field in HANDOFF_PHASE_TIMING_FIELDS)
    if abs(phase_total - safe["total_browser_ready_ms"]) > len(HANDOFF_PHASE_TIMING_FIELDS):
        raise HandoffError("Handoff timing phases did not match the total")
    peer_total = sum(safe[field] for field in PEER_SETUP_TIMING_FIELDS)
    if abs(peer_total - safe["peer_setup_ms"]) > len(PEER_SETUP_TIMING_FIELDS):
        raise HandoffError("Peer setup timing subphases did not match the aggregate")
    return safe


def _sanitize_input_level(detail: dict[str, object]) -> dict[str, object]:
    phase = detail.get("phase")
    rms = detail.get("rms")
    peak = detail.get("peak")
    sample_count = detail.get("sampleCount")
    if phase not in INPUT_LEVEL_PHASES:
        raise HandoffError("Input-level phase was invalid")
    if (
        isinstance(rms, bool)
        or not isinstance(rms, (int, float))
        or not math.isfinite(float(rms))
        or not 0.0 <= float(rms) <= 1.0
    ):
        raise HandoffError("Input-level RMS was invalid")
    if (
        isinstance(peak, bool)
        or not isinstance(peak, (int, float))
        or not math.isfinite(float(peak))
        or not 0.0 <= float(peak) <= 1.0
    ):
        raise HandoffError("Input-level peak was invalid")
    if (
        isinstance(sample_count, bool)
        or not isinstance(sample_count, int)
        or not 1 <= sample_count <= MAX_INPUT_LEVEL_SAMPLE_COUNT
    ):
        raise HandoffError("Input-level sample count was invalid")
    return {
        "phase": phase,
        "rms": round(float(rms), 4),
        "peak": round(float(peak), 4),
        "sampleCount": sample_count,
    }


def _sanitize_negotiation_error(detail: dict[str, object]) -> dict[str, object]:
    http_status = detail.get("httpStatus")
    if (
        isinstance(http_status, bool)
        or not isinstance(http_status, int)
        or not 400 <= http_status <= 599
    ):
        raise HandoffError("Negotiation HTTP status was invalid")
    safe: dict[str, object] = {
        "reason": "webrtc_negotiation_failed",
        "httpStatus": http_status,
    }
    for key in NEGOTIATION_DIAGNOSTIC_FIELDS:
        value = detail.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not _SAFE_VALUE.fullmatch(value):
            raise HandoffError(f"Negotiation diagnostic {key} was invalid")
        safe[key] = value
    return safe


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


def _calculator_output(name: object, arguments: object) -> str:
    """Execute only the existing safe calculator and return bounded JSON output."""

    if name != "calculator":
        return json.dumps({"status": "error", "answer": "Unsupported Realtime tool."})
    if not isinstance(arguments, str) or len(arguments) > MAX_TOOL_ARGUMENT_CHARS:
        return json.dumps({"status": "error", "answer": "Calculator arguments were invalid."})
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict) or set(payload) != {"expression"}:
        return json.dumps({"status": "error", "answer": "Calculator arguments were invalid."})
    expression = payload.get("expression")
    if not isinstance(expression, str) or not expression.strip() or len(expression) > MAX_CALCULATOR_EXPRESSION_CHARS:
        return json.dumps({"status": "error", "answer": "Calculator expression was invalid."})
    result = execute_route(ToolRoute("calculator", "safe_calculator", {"expression": expression.strip()}))
    return json.dumps({"status": result.status, "answer": result.answer}, ensure_ascii=False)

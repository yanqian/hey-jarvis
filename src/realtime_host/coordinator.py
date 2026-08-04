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
from datetime import datetime
from enum import Enum
from typing import Callable, Protocol

from src.tools import ProviderConfig, ToolRoute, execute_route
from src.tools.router import FX_SUPPORTED_CURRENCIES


MAX_EVIDENCE_EVENTS = 200
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
MAX_TRANSCRIPT_CONTROL_CHARS = 200
MAX_NORMALIZED_END_PHRASE_CHARS = 64
MAX_TOOL_ARGUMENT_CHARS = 512
MAX_CALCULATOR_EXPRESSION_CHARS = 200
MAX_WEATHER_LOCATION_CHARS = 100
MAX_FX_AMOUNT = 1_000_000_000
_SAFE_STOCK_SYMBOL = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z])?$")
MAX_TOOL_OUTPUT_CHARS = 4096
MAX_INPUT_LEVEL_SAMPLE_COUNT = 10
MAX_FIXTURE_AUDIO_BYTES = 384_000
MAX_HANDOFF_TIMING_MS = 60_000
FIXTURE_AUDIO_NAMES = frozenset({"turn-1", "turn-2"})
INPUT_LEVEL_PHASES = frozenset({"no_remote_playback", "remote_playback"})
LOCAL_TIMING_MARKERS = frozenset({"wake_confirmed", "ack_started", "ack_completed"})
ACKNOWLEDGEMENT_MODES = frozenset({"local", "realtime"})
ACKNOWLEDGEMENT_CAPTURE_LABEL = re.compile(r"^candidate-[0-9]{2}$")
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
REMOVED_TOKEN_TIMING_FIELDS = frozenset({"command_to_token_ms", "token_ms"})
PEER_SETUP_TIMING_FIELDS = frozenset(
    {
        "microphone_reporting_ms",
        "audio_analysis_setup_ms",
        "peer_connection_setup_ms",
        "offer_creation_ms",
        "local_description_ms",
    }
)
AUDIO_ANALYSIS_TIMING_FIELDS = frozenset(
    {
        "input_level_cleanup_ms",
        "audio_context_creation_ms",
        "analyser_setup_ms",
        "media_stream_source_creation_ms",
        "source_connection_ms",
        "monitor_startup_ms",
    }
)
HANDOFF_TIMING_FIELDS = frozenset(
    {
        *HANDOFF_PHASE_TIMING_FIELDS,
        *PEER_SETUP_TIMING_FIELDS,
        *AUDIO_ANALYSIS_TIMING_FIELDS,
        "data_channel_open_ms",
        "session_created_after_data_channel_open_ms",
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
    HOST_READY = "host_ready"
    HOST_ACTIVE = "host_active"
    HOST_FAREWELL = "host_farewell"
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
        acknowledgement_mode: str = "local",
        end_phrases: tuple[str, ...] = (),
        tool_provider_config: object | None = None,
        tool_http_client: object | None = None,
        tool_now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if acknowledgement_mode not in ACKNOWLEDGEMENT_MODES:
            raise ValueError("acknowledgement_mode must be 'realtime' or 'local'")
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
        self._input_enable_requested = False
        self._acknowledgement_mode = acknowledgement_mode
        self._next_acknowledgement_mode: str | None = None
        self._active_acknowledgement_mode = "local"
        self._next_acknowledgement_capture_label: str | None = None
        self._active_acknowledgement_capture_label: str | None = None
        self._acknowledgement_capture_saved = False
        self._realtime_ack_response_created = False
        self._realtime_ack_response_done = False
        self._realtime_ack_playback_started = False
        self._realtime_ack_playback_stopped = False
        self._connected_at: float | None = None
        self._last_activity_at: float | None = None
        self._assistant_playback_active = False
        self._farewell_started_at: float | None = None
        self._farewell_response_created = False
        self._farewell_response_done = False
        self._farewell_playback_started = False
        self._farewell_playback_stopped = False
        self._handoff_timing_received = False
        self._input_level_diagnostics_next = False
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
        self._tool_provider_config = tool_provider_config or ProviderConfig()
        self._tool_http_client = tool_http_client
        self._tool_now_provider = tool_now_provider
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

    def record_local_timing_marker(
        self,
        marker: str,
        *,
        ack_asset_duration_ms: int | None = None,
    ) -> None:
        """Record one privacy-safe local wake/ack boundary."""

        with self._lock:
            if marker not in LOCAL_TIMING_MARKERS:
                raise HandoffError("Local timing marker was invalid")
            if ack_asset_duration_ms is not None:
                if marker != "ack_started":
                    raise HandoffError("Acknowledgement duration belongs only on ack_started")
                if (
                    isinstance(ack_asset_duration_ms, bool)
                    or not isinstance(ack_asset_duration_ms, int)
                    or not 1 <= ack_asset_duration_ms <= MAX_HANDOFF_TIMING_MS
                ):
                    raise HandoffError("Acknowledgement duration was invalid")
                self._record(marker, ack_asset_duration_ms=ack_asset_duration_ms)
            else:
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

    def request_input_level_diagnostics(self) -> None:
        """Enable bounded input-level monitoring for exactly the next handoff."""

        with self._lock:
            if not self._armed:
                raise HandoffError("WebRTC host must be armed before input-level diagnosis")
            if self._state != HandoffState.WAKE_OWNED or self._session_id is not None:
                raise HandoffError(
                    "Input-level diagnosis can only be enabled while wake owns the microphone"
                )
            self._input_level_diagnostics_next = True
            self._record("input_level_diagnostics_armed")

    def request_realtime_acknowledgement_experiment(self) -> None:
        """Use one Realtime-native acknowledgement on the next handoff only."""

        with self._lock:
            if not self._armed:
                raise HandoffError("WebRTC host must be armed before acknowledgement evaluation")
            if self._state != HandoffState.WAKE_OWNED or self._session_id is not None:
                raise HandoffError(
                    "Realtime acknowledgement evaluation can only be armed while wake owns the microphone"
                )
            if self._next_acknowledgement_capture_label is not None:
                raise HandoffError("Acknowledgement capture is already armed")
            self._next_acknowledgement_mode = "realtime"
            self._record("realtime_acknowledgement_experiment_armed")

    def request_realtime_acknowledgement_capture(self, label: str) -> None:
        """Digitally capture exactly one correlated Realtime ACK on the next handoff."""

        with self._lock:
            if not self._armed:
                raise HandoffError("WebRTC host must be armed before acknowledgement capture")
            if self._state != HandoffState.WAKE_OWNED or self._session_id is not None:
                raise HandoffError(
                    "Realtime acknowledgement capture can only be armed while wake owns the microphone"
                )
            if not isinstance(label, str) or not ACKNOWLEDGEMENT_CAPTURE_LABEL.fullmatch(label):
                raise HandoffError("Acknowledgement capture label was invalid")
            if self._next_acknowledgement_capture_label is not None:
                raise HandoffError("Acknowledgement capture is already armed")
            self._next_acknowledgement_mode = "realtime"
            self._next_acknowledgement_capture_label = label
            self._record("realtime_acknowledgement_capture_armed", candidate=label)

    def validate_realtime_acknowledgement_capture(self, label: str) -> None:
        with self._lock:
            self._validate_realtime_acknowledgement_capture(label)

    def accept_realtime_acknowledgement_capture(self, label: str) -> None:
        """Correlate one saved candidate without retaining its bytes or transcript in evidence."""

        with self._lock:
            self._validate_realtime_acknowledgement_capture(label)
            self._acknowledgement_capture_saved = True
            self._record("host_acknowledgement_candidate_saved", candidate=label)

    def _validate_realtime_acknowledgement_capture(self, label: str) -> None:
        if (
            self._state != HandoffState.HOST_READY
            or label != self._active_acknowledgement_capture_label
            or self._acknowledgement_capture_saved
            or not self._realtime_ack_response_created
            or not self._realtime_ack_playback_started
        ):
            raise HandoffError("Acknowledgement candidate upload was stale or uncorrelated")

    @property
    def active_acknowledgement_mode(self) -> str:
        with self._lock:
            return self._active_acknowledgement_mode

    @property
    def realtime_acknowledgement_complete(self) -> bool:
        with self._lock:
            return (
                self._active_acknowledgement_mode == "realtime"
                and self._realtime_ack_response_done
                and self._realtime_ack_playback_started
                and self._realtime_ack_playback_stopped
                and (
                    self._active_acknowledgement_capture_label is None
                    or self._acknowledgement_capture_saved
                )
            )

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
            self._input_enable_requested = False
            self._active_acknowledgement_mode = (
                self._next_acknowledgement_mode or self._acknowledgement_mode
            )
            self._next_acknowledgement_mode = None
            self._active_acknowledgement_capture_label = self._next_acknowledgement_capture_label
            self._next_acknowledgement_capture_label = None
            self._acknowledgement_capture_saved = False
            self._reset_realtime_acknowledgement()
            self._connected_at = None
            self._last_activity_at = self._clock()
            self._assistant_playback_active = False
            self._reset_farewell()
            self._handoff_timing_received = False
            self._seen_transcription_items.clear()
            self._handled_tool_calls.clear()
            self._state = HandoffState.HOST_STARTING
            input_level_diagnostics = self._input_level_diagnostics_next
            self._input_level_diagnostics_next = False
            self._record("handoff_queued", session_id=session_id)
            detail: dict[str, object] = {}
            if input_level_diagnostics:
                detail["input_level_diagnostics"] = True
            if self._active_acknowledgement_mode == "realtime":
                detail["acknowledgement_mode"] = "realtime"
            if self._active_acknowledgement_capture_label is not None:
                detail["acknowledgement_capture_label"] = self._active_acknowledgement_capture_label
            self._enqueue("start", session_id, **detail)
            return session_id

    def enable_host_input(self) -> None:
        """Open browser input only after configuration and local acknowledgement."""

        with self._lock:
            if self._session_id is None or self._state != HandoffState.HOST_READY:
                raise HandoffError("Host input can only be enabled after session configuration")
            if self._input_enable_requested:
                raise HandoffError("Host input enablement was already requested")
            self._input_enable_requested = True
            self._enqueue("enable_input", self._session_id)

    def request_stop(self, reason: str = "requested") -> None:
        with self._lock:
            if self._session_id is None or self._state == HandoffState.WAKE_OWNED:
                return
            if self._state != HandoffState.HOST_STOPPING:
                self._state = HandoffState.HOST_STOPPING
                self._enqueue("stop", self._session_id, reason=reason)

    def timeout_reason(
        self,
        *,
        idle_seconds: float,
        max_duration_seconds: float,
        farewell_seconds: float = 8.0,
    ) -> str | None:
        with self._lock:
            if self._state not in {HandoffState.HOST_ACTIVE, HandoffState.HOST_FAREWELL}:
                return None
            if self._connected_at is None:
                return None
            now = self._clock()
            if now - self._connected_at >= max_duration_seconds:
                return "max_duration"
            if self._state == HandoffState.HOST_FAREWELL:
                if self._farewell_started_at is None:
                    return "farewell_state_error"
                if now - self._farewell_started_at >= farewell_seconds:
                    return "farewell_timeout"
                return None
            if self._assistant_playback_active:
                return None
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
        if event_type == "tool_call":
            return self._handle_tool_call(
                session_id,
                host_id=host_id,
                detail=detail,
            )
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
            if event_type == "session_configured":
                if self._state != HandoffState.HOST_STARTING:
                    raise HandoffError("Session configuration readiness was duplicated or late")
                if not self._transport_connected or not self._session_created:
                    raise HandoffError("Session configured before transport and session creation")
            if event_type == "connected":
                if self._state != HandoffState.HOST_READY or not self._input_enable_requested:
                    raise HandoffError("Host reported input ready before enablement")
            if event_type in {
                "fixture_submitted",
                "speech_started",
                "speech_stopped",
                "response_created",
                "response_done",
                "playback_started",
                "playback_stopped",
                "transcription",
                "transcription_failed",
                "tool_call",
            } and self._state in {HandoffState.HOST_STARTING, HandoffState.HOST_READY}:
                raise HandoffError("Host user-turn activity arrived before input readiness")
            if event_type == "transcription":
                return self._handle_completed_transcription(session_id, detail)
            if self._state == HandoffState.HOST_FAREWELL and event_type in {
                "speech_started",
                "speech_stopped",
                "fixture_submitted",
            }:
                self._record(
                    "host_farewell_input_ignored",
                    session_id=session_id,
                    reason=event_type,
                )
                return "farewell"
            if event_type == "transcription_failed":
                self._record("host_transcription_failed", session_id=session_id, reason="provider_failure")
                self._last_activity_at = self._clock()
                return "accepted"
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
                    if key
                    in {
                        "echoCancellation",
                        "echoCancellationRequested",
                        "echoCancellationAllSupported",
                        "noiseSuppression",
                        "autoGainControl",
                        "inputNoiseReduction",
                        "sampleRate",
                        "channelCount",
                        "outputVolume",
                        "reason",
                    }
                    and isinstance(value, (str, int, float, bool))
                }
            self._record(f"host_{event_type}", session_id=session_id, **safe_detail)
            if event_type == "connected":
                self._state = HandoffState.HOST_ACTIVE
                self._connected_at = self._clock()
                self._last_activity_at = self._connected_at
            elif event_type == "transport_connected":
                self._transport_connected = True
            elif event_type == "session_created":
                self._session_created = True
            elif event_type == "session_configured":
                self._session_configured = True
                self._state = HandoffState.HOST_READY
            if event_type == "playback_started":
                self._assistant_playback_active = True
            elif event_type == "playback_stopped":
                self._assistant_playback_active = False
            if event_type in {
                "fixture_submitted",
                "speech_started",
                "speech_stopped",
                "response_created",
                "response_done",
                "playback_started",
                "playback_stopped",
                "transcription",
            }:
                self._last_activity_at = self._clock()
            if event_type == "error":
                self.request_stop(str(safe_detail.get("reason", "host_error")))
            elif event_type == "stopped":
                self._finish_handoff(event_type)
            elif event_type == "farewell_started":
                if self._state != HandoffState.HOST_FAREWELL:
                    raise HandoffError("Farewell started outside the farewell phase")
            elif event_type == "farewell_response_created":
                if self._state != HandoffState.HOST_FAREWELL or self._farewell_response_created:
                    raise HandoffError("Farewell response creation was duplicated or out of order")
                self._farewell_response_created = True
            elif event_type == "farewell_response_done":
                if self._state != HandoffState.HOST_FAREWELL or not self._farewell_response_created:
                    raise HandoffError("Farewell response completion was out of order")
                reason = str(safe_detail.get("reason", "unknown"))
                if reason != "completed":
                    self.request_stop("farewell_response_failed")
                else:
                    self._farewell_response_done = True
                    self._finish_farewell_if_ready()
            elif event_type == "farewell_playback_started":
                if self._state != HandoffState.HOST_FAREWELL or not self._farewell_response_created:
                    raise HandoffError("Farewell playback started out of order")
                self._farewell_playback_started = True
            elif event_type == "farewell_playback_stopped":
                if self._state != HandoffState.HOST_FAREWELL or not self._farewell_playback_started:
                    raise HandoffError("Farewell playback completion was out of order")
                self._farewell_playback_stopped = True
                self._finish_farewell_if_ready()
            elif event_type == "realtime_ack_response_created":
                if (
                    self._state != HandoffState.HOST_READY
                    or self._active_acknowledgement_mode != "realtime"
                    or self._realtime_ack_response_created
                ):
                    raise HandoffError("Realtime acknowledgement response creation was unexpected")
                self._realtime_ack_response_created = True
            elif event_type == "realtime_ack_response_done":
                if self._state != HandoffState.HOST_READY or not self._realtime_ack_response_created:
                    raise HandoffError("Realtime acknowledgement response completion was out of order")
                if str(safe_detail.get("reason", "unknown")) != "completed":
                    self.request_stop("realtime_acknowledgement_failed")
                else:
                    self._realtime_ack_response_done = True
            elif event_type == "realtime_ack_playback_started":
                if self._state != HandoffState.HOST_READY or not self._realtime_ack_response_created:
                    raise HandoffError("Realtime acknowledgement playback was out of order")
                self._realtime_ack_playback_started = True
            elif event_type == "realtime_ack_playback_stopped":
                if self._state != HandoffState.HOST_READY or not self._realtime_ack_playback_started:
                    raise HandoffError("Realtime acknowledgement playback completion was out of order")
                self._realtime_ack_playback_stopped = True
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
            self._begin_farewell(session_id, reason="exact_phrase")
            return "farewell"
        return "accepted"

    def _handle_tool_call(
        self,
        session_id: str | None,
        *,
        host_id: str | None,
        detail: dict[str, object],
    ) -> str:
        """Claim under the lifecycle lock, execute outside it, then correlate safely."""

        with self._lock:
            if host_id != self._host_id:
                raise HandoffError("Host event did not match the armed host")
            if session_id != self._session_id or self._session_id is None:
                raise HandoffError("Host event did not match the active session")
            if self._state in {HandoffState.HOST_STARTING, HandoffState.HOST_READY}:
                raise HandoffError("Host user-turn activity arrived before input readiness")
            call_id = detail.get("call_id")
            name = detail.get("name")
            arguments = detail.get("arguments")
            if not isinstance(call_id, str) or not _SAFE_VALUE.fullmatch(call_id):
                raise HandoffError("Realtime tool call identity was invalid")
            if call_id in self._handled_tool_calls:
                self._record("host_tool_call_duplicate", session_id=session_id)
                if self._state == HandoffState.HOST_FAREWELL:
                    return "farewell"
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
                self._begin_farewell(session_id, reason="semantic")
                return "farewell"
            if self._state != HandoffState.HOST_ACTIVE:
                self._record(
                    "host_tool_call_ignored",
                    session_id=session_id,
                    reason="late_event",
                )
                return "stopping"
            self._record("host_tool_call_started", session_id=session_id)
            self._last_activity_at = self._clock()

        output = _realtime_tool_output(
            name,
            arguments,
            provider_config=self._tool_provider_config,
            http_client=self._tool_http_client,
            now_provider=self._tool_now_provider,
        )

        with self._lock:
            if session_id != self._session_id or self._state != HandoffState.HOST_ACTIVE:
                self._record(
                    "host_tool_result_ignored",
                    session_id=session_id,
                    reason="late_or_stale",
                )
                return "stopping" if self._state == HandoffState.HOST_STOPPING else "accepted"
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

    def availability(self) -> str:
        """Return the bounded, user-facing availability of local voice input."""
        with self._lock:
            if not self._armed:
                return "ready"
            if self._state == HandoffState.WAKE_OWNED:
                return "wake_listening" if self._wake_lease.is_open else "resume_required"
            if self._state in {
                HandoffState.HOST_STARTING,
                HandoffState.HOST_READY,
                HandoffState.HOST_ACTIVE,
                HandoffState.HOST_FAREWELL,
                HandoffState.HOST_STOPPING,
            }:
                return "busy"
            return "resume_required"

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
        self._input_enable_requested = False
        self._active_acknowledgement_mode = "local"
        self._active_acknowledgement_capture_label = None
        self._acknowledgement_capture_saved = False
        self._reset_realtime_acknowledgement()
        self._connected_at = None
        self._last_activity_at = None
        self._assistant_playback_active = False
        self._reset_farewell()
        self._handoff_timing_received = False
        self._seen_transcription_items.clear()
        self._handled_tool_calls.clear()
        if not self._wake_lease.is_open:
            self._wake_lease.open()
        self._state = HandoffState.WAKE_OWNED
        self._record("wake_microphone_reopened", session_id=session_id, result=result)

    def _begin_farewell(self, session_id: str, *, reason: str) -> None:
        if self._state == HandoffState.HOST_FAREWELL:
            return
        if self._state != HandoffState.HOST_ACTIVE or session_id != self._session_id:
            raise HandoffError("Farewell requires the active session")
        self._state = HandoffState.HOST_FAREWELL
        self._farewell_started_at = self._clock()
        self._farewell_response_created = False
        self._farewell_response_done = False
        self._farewell_playback_started = False
        self._farewell_playback_stopped = False
        self._record("host_farewell_requested", session_id=session_id, reason=reason)

    def _finish_farewell_if_ready(self) -> None:
        if (
            self._state == HandoffState.HOST_FAREWELL
            and self._farewell_response_done
            and self._farewell_playback_started
            and self._farewell_playback_stopped
        ):
            self._record("host_farewell_completed", session_id=self._session_id)
            self.request_stop("farewell_complete")

    def _reset_farewell(self) -> None:
        self._farewell_started_at = None
        self._farewell_response_created = False
        self._farewell_response_done = False
        self._farewell_playback_started = False
        self._farewell_playback_stopped = False

    def _reset_realtime_acknowledgement(self) -> None:
        self._realtime_ack_response_created = False
        self._realtime_ack_response_done = False
        self._realtime_ack_playback_started = False
        self._realtime_ack_playback_stopped = False

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
    if any(safe[field] != 0 for field in REMOVED_TOKEN_TIMING_FIELDS):
        raise HandoffError("Removed token timing phases must be zero")
    phase_total = sum(safe[field] for field in HANDOFF_PHASE_TIMING_FIELDS)
    if abs(phase_total - safe["total_browser_ready_ms"]) > len(HANDOFF_PHASE_TIMING_FIELDS):
        raise HandoffError("Handoff timing phases did not match the total")
    peer_total = sum(safe[field] for field in PEER_SETUP_TIMING_FIELDS)
    if abs(peer_total - safe["peer_setup_ms"]) > len(PEER_SETUP_TIMING_FIELDS):
        raise HandoffError("Peer setup timing subphases did not match the aggregate")
    audio_analysis_total = sum(safe[field] for field in AUDIO_ANALYSIS_TIMING_FIELDS)
    if (
        abs(audio_analysis_total - safe["audio_analysis_setup_ms"])
        > len(AUDIO_ANALYSIS_TIMING_FIELDS)
    ):
        raise HandoffError("Audio analysis timing subphases did not match the aggregate")
    readiness_total = (
        safe["data_channel_open_ms"]
        + safe["session_created_after_data_channel_open_ms"]
    )
    if readiness_total != safe["session_configuration_ms"]:
        raise HandoffError("Realtime readiness timing subphases did not match the aggregate")
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


def _realtime_tool_output(
    name: object,
    arguments: object,
    *,
    provider_config: object,
    http_client: object | None,
    now_provider: Callable[[], datetime] | None,
) -> str:
    """Execute one allowlisted existing tool and return bounded JSON output."""

    if name not in {"calculator", "weather", "local_time", "fx", "stock"}:
        return json.dumps({"status": "error", "answer": "Unsupported Realtime tool."})
    if not isinstance(arguments, str) or len(arguments) > MAX_TOOL_ARGUMENT_CHARS:
        return _invalid_tool_arguments(name)
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError:
        payload = None
    if name == "calculator":
        if not isinstance(payload, dict) or set(payload) != {"expression"}:
            return _invalid_tool_arguments(name)
        expression = payload.get("expression")
        if (
            not isinstance(expression, str)
            or not expression.strip()
            or len(expression) > MAX_CALCULATOR_EXPRESSION_CHARS
        ):
            return json.dumps({"status": "error", "answer": "Calculator expression was invalid."})
        result = execute_route(
            ToolRoute("calculator", "safe_calculator", {"expression": expression.strip()})
        )
        return _bounded_tool_output(result.status, result.answer)

    if name == "local_time":
        if payload != {}:
            return _invalid_tool_arguments(name)
        result = execute_route(
            ToolRoute("time", "local_time", {"timezone": "local"}),
            now_provider=now_provider,
        )
        return _bounded_tool_output(result.status, result.answer, data=result.data)

    if name == "fx":
        if not isinstance(payload, dict) or not set(payload).issubset(
            {"amount", "base", "quote"}
        ):
            return _invalid_tool_arguments(name)
        amount = payload.get("amount")
        if amount is not None and (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
            or amount <= 0
            or amount > MAX_FX_AMOUNT
        ):
            return _invalid_tool_arguments(name)
        params = {"query": "realtime foreign exchange request"}
        if amount is not None:
            params["amount"] = str(amount)
        for currency_name in ("base", "quote"):
            currency = payload.get(currency_name)
            if currency is None:
                continue
            if (
                not isinstance(currency, str)
                or currency != currency.strip().upper()
                or currency not in FX_SUPPORTED_CURRENCIES
            ):
                return _invalid_tool_arguments(name)
            params[currency_name] = currency
        result = execute_route(
            ToolRoute("fx", "fx_provider", params),
            provider_config=provider_config,
            http_client=http_client,
        )
        return _bounded_tool_output(result.status, result.answer, data=result.data)

    if name == "stock":
        if not isinstance(payload, dict) or set(payload) != {"symbol"}:
            return _invalid_tool_arguments(name)
        symbol = payload.get("symbol")
        if not isinstance(symbol, str) or not _SAFE_STOCK_SYMBOL.fullmatch(symbol):
            return _invalid_tool_arguments(name)
        result = execute_route(
            ToolRoute(
                "stock",
                "stock_provider",
                {"query": "realtime stock quote request", "symbol": symbol},
            ),
            provider_config=provider_config,
            http_client=http_client,
        )
        return _bounded_tool_output(result.status, result.answer, data=result.data)

    if not isinstance(payload, dict) or not set(payload).issubset({"location", "intent"}):
        return _invalid_tool_arguments(name)
    intent = payload.get("intent")
    location = payload.get("location")
    if intent not in {"current", "today", "tomorrow"}:
        return _invalid_tool_arguments(name)
    if location is not None and (
        not isinstance(location, str)
        or not location.strip()
        or len(location) > MAX_WEATHER_LOCATION_CHARS
    ):
        return _invalid_tool_arguments(name)
    params = {"intent": str(intent), "query": "realtime weather request"}
    if isinstance(location, str):
        params["location"] = location.strip()
    result = execute_route(
        ToolRoute("weather", "weather_provider", params),
        provider_config=provider_config,
        http_client=http_client,
    )
    return _bounded_tool_output(result.status, result.answer, data=result.data)


def _invalid_tool_arguments(name: object) -> str:
    label = {
        "calculator": "Calculator",
        "weather": "Weather",
        "local_time": "Local time",
        "fx": "FX",
        "stock": "Stock",
    }.get(name, "Tool")
    return json.dumps({"status": "error", "answer": f"{label} arguments were invalid."})


def _bounded_tool_output(
    status: str,
    answer: str,
    *,
    data: object | None = None,
) -> str:
    payload: dict[str, object] = {"status": status, "answer": answer}
    if isinstance(data, dict):
        payload["data"] = data
    output = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(output) <= MAX_TOOL_OUTPUT_CHARS:
        return output
    return json.dumps(
        {"status": "error", "answer": "Realtime tool output was too large."},
        separators=(",", ":"),
    )

"""Loopback control server for the development Chrome app-mode WebRTC host."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Mapping

from src.audio_input import open_microphone_stream
from src.config import ConfigError, DEFAULT_REALTIME_END_PHRASES, load_settings
from src.english_voice_cues import EnglishVoiceCueError, load_candidate as load_english_voice_cue
from src.realtime_host.coordinator import HandoffCoordinator, HandoffError, SoundDeviceWakeLease
from src.realtime_ack_asset import (
    RealtimeAckAssetError,
    load_selected_asset as load_acknowledgement_asset,
    store_candidate as store_acknowledgement_candidate,
)
from src.realtime_farewell_asset import (
    RealtimeFarewellAssetError,
    load_selected_asset as load_farewell_asset,
)
from src.session_expiry_cues import (
    SessionExpiryCueError,
    load_selected_asset as load_session_expiry_cue,
)
from src.tools.router import FX_SUPPORTED_CURRENCIES


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8770
DEFAULT_MODEL = "gpt-realtime-2.1"
DEFAULT_VOICE = "marin"
REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
MAX_SDP_BYTES = 128_000
CHROME_BINARY = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
STATIC_ROOT = Path(__file__).resolve().parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
    "/negotiation-diagnostics.js": ("negotiation-diagnostics.js", "text/javascript; charset=utf-8"),
    "/failure-guidance.js": ("failure-guidance.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class HostServerError(RuntimeError):
    pass


class RealtimeCallError(HostServerError):
    """Privacy-safe summary of one rejected upstream Realtime call."""

    def __init__(
        self,
        http_status: int,
        *,
        provider_error_type: str | None = None,
        provider_error_code: str | None = None,
    ) -> None:
        super().__init__(f"OpenAI Realtime call failed with HTTP {http_status}")
        self.http_status = http_status
        self.provider_error_type = provider_error_type
        self.provider_error_code = provider_error_code

    def safe_payload(self) -> dict[str, object]:
        error: dict[str, object] = {
            "type": "realtime_call_failed",
            "upstream_http_status": self.http_status,
        }
        if self.provider_error_type is not None:
            error["provider_error_type"] = self.provider_error_type
        if self.provider_error_code is not None:
            error["provider_error_code"] = self.provider_error_code
        return {"error": error}


class MemoryWakeLease:
    """Dependency-free default lease; --real-microphone exercises sounddevice ownership."""

    def __init__(self) -> None:
        self.is_open = False

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False


def read_app_language(path: Path | None) -> str:
    if not isinstance(path, Path):
        return "en"
    try:
        raw = path.read_bytes()
        if len(raw) > 4096:
            return "en"
        value = json.loads(raw).get("app_language")
    except (OSError, ValueError, AttributeError):
        return "en"
    return value if value in {"en", "zh-CN"} else "en"


def read_app_theme(path: Path | None) -> str:
    if not isinstance(path, Path):
        return "night"
    try:
        raw = path.read_bytes()
        if len(raw) > 4096:
            return "night"
        value = json.loads(raw).get("app_theme")
    except (OSError, ValueError, AttributeError):
        return "night"
    return value if value in {"night", "day"} else "night"


def load_host_config(env: Mapping[str, str] | None = None, env_file: str | Path = ".env") -> tuple[str, str, str]:
    values = _read_env_file(Path(env_file))
    values.update(os.environ if env is None else env)
    key = values.get("OPENAI_API_KEY", "").strip().strip("'\"")
    if not key or key in {"your_api_key_here", "replace_me", "changeme"}:
        raise HostServerError("OPENAI_API_KEY is required in .env or the environment")
    return (
        key,
        values.get("REALTIME_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        values.get("REALTIME_VOICE", DEFAULT_VOICE).strip() or DEFAULT_VOICE,
    )


def build_realtime_session_config(settings: object) -> dict[str, object]:
    turn_detection = (
        {
            "type": "server_vad",
            "threshold": settings.realtime_server_vad_threshold,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 500,
            "create_response": True,
            "interrupt_response": True,
        }
        if settings.realtime_server_vad_enabled
        else None
    )
    input_audio: dict[str, object] = {"turn_detection": turn_detection}
    input_audio["noise_reduction"] = (
        None
        if settings.realtime_input_noise_reduction == "none"
        else {"type": settings.realtime_input_noise_reduction}
    )
    if settings.realtime_input_transcription_enabled:
        input_audio["transcription"] = {"model": settings.transcribe_model}
    instructions = "\n".join(
        (
            "# Role & Objective",
            "- Be a concise, natural voice assistant.",
            "# Language",
            "- For every turn, respond in the language primarily used in the user's current utterance.",
            "- For Mandarin Chinese input, answer entirely in concise, natural Simplified Chinese.",
            "- For English input, answer in English.",
            "- The current user utterance overrides prior turns, these English instructions, English tool definitions, and English tool outputs.",
            "- For mixed or ambiguous input, use the language of the main request; never default to English merely because developer or tool text is English.",
            "- If the user explicitly asks for translation, spelling, pronunciation, language practice, or a whole response in another language, include or use the requested target language. Unless the whole response is requested in that language, keep the surrounding explanation in the language of the current request.",
            "# Conversation Ending",
            "- If the user clearly and unambiguously wants to end the current conversation, call end_conversation with {} and do not speak before the tool result. The client will request one brief farewell after muting input.",
            "- Do not call end_conversation when farewell words are merely mentioned, quoted, translated, or requested as content.",
        )
    )
    tools = [
        {
            "type": "function",
            "name": "calculator",
            "description": "Safely evaluate one arithmetic expression. Use only for arithmetic.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Arithmetic expression using numbers, parentheses, +, -, *, /, //, %, or **.",
                    }
                },
                "required": ["expression"],
            },
        },
        {
            "type": "function",
            "name": "weather",
            "description": (
                "Get current, today, or tomorrow weather from the configured provider. "
                "Pass a location only when the user explicitly names one; otherwise omit it "
                "so the server uses its configured default location. Translate an explicit "
                "non-English place into its common provider-friendly English name when known, "
                "for example 东京 or 東京 becomes Tokyo."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Explicit city or place named by the user.",
                    },
                    "intent": {
                        "type": "string",
                        "enum": ["current", "today", "tomorrow"],
                        "description": "Requested weather time horizon.",
                    },
                },
                "required": ["intent"],
            },
        },
        {
            "type": "function",
            "name": "local_time",
            "description": (
                "Get the current local date, time, and timezone from the host. "
                "Use only for the host's local time; this tool does not accept a location or timezone."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
        {
            "type": "function",
            "name": "fx",
            "description": (
                "Convert an amount between supported currencies using the latest available "
                "Frankfurter reference rate. Omit base or quote only when the user does not "
                "specify it so the server can apply its configured currency defaults."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "amount": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 1_000_000_000,
                        "description": "Positive amount to convert; omit to use 1.",
                    },
                    "base": {
                        "type": "string",
                        "enum": list(FX_SUPPORTED_CURRENCIES),
                        "description": "Source currency code explicitly named by the user.",
                    },
                    "quote": {
                        "type": "string",
                        "enum": list(FX_SUPPORTED_CURRENCIES),
                        "description": "Target currency code explicitly named by the user.",
                    },
                },
            },
        },
        {
            "type": "function",
            "name": "stock",
            "description": (
                "Get the latest available Finnhub quote for one explicitly requested stock "
                "ticker. Resolve a clearly named company to its conservative ticker when known. "
                "This returns market data only and cannot place trades or give financial advice."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "symbol": {
                        "type": "string",
                        "pattern": "^[A-Z]{1,5}(?:\\.[A-Z])?$",
                        "maxLength": 7,
                        "description": "One uppercase stock ticker, for example AAPL or BRK.B.",
                    },
                },
                "required": ["symbol"],
            },
        },
        {
            "type": "function",
            "name": "end_conversation",
            "description": "End the current voice session only when the user clearly and unambiguously wants to leave, stop, say goodbye, or end this conversation. Do not use when the user merely mentions, quotes, translates, or asks you to say a farewell phrase.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
    ]
    return {
        "type": "realtime",
        "model": settings.realtime_model,
        "instructions": instructions,
        "output_modalities": ["audio"],
        "audio": {
            "input": input_audio,
            "output": {"voice": settings.realtime_voice},
        },
        "tools": tools,
        "tool_choice": "auto",
    }


def _multipart_call_body(
    sdp: str,
    session: Mapping[str, object],
    *,
    boundary: str,
) -> bytes:
    parts: list[bytes] = []
    for name, content_type, value in (
        ("sdp", "application/sdp", sdp.encode("utf-8")),
        (
            "session",
            "application/json",
            json.dumps(session, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        ),
    ):
        parts.extend(
            (
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n'.encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                value,
                b"\r\n",
            )
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


def create_realtime_call(
    *,
    api_key: str,
    sdp: str,
    session: Mapping[str, object],
    urlopen: Callable[..., object] = urllib.request.urlopen,
    boundary: str | None = None,
) -> str:
    multipart_boundary = boundary or f"hey-jarvis-{uuid.uuid4().hex}"
    request = urllib.request.Request(
        REALTIME_CALLS_URL,
        data=_multipart_call_body(sdp, session, boundary=multipart_boundary),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={multipart_boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            answer = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        provider_type, provider_code = _safe_realtime_error_fields(exc)
        raise RealtimeCallError(
            exc.code,
            provider_error_type=provider_type,
            provider_error_code=provider_code,
        ) from exc
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise HostServerError("OpenAI Realtime call failed safely") from exc
    if not answer.startswith("v=0") or len(answer.encode("utf-8")) > MAX_SDP_BYTES:
        raise HostServerError("OpenAI Realtime SDP answer was malformed")
    return answer


def _safe_realtime_error_fields(error: urllib.error.HTTPError) -> tuple[str | None, str | None]:
    try:
        raw = error.read(4097)
    except (OSError, ValueError):
        return None, None
    finally:
        error.close()
    if len(raw) > 4096:
        return None, None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    provider_error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(provider_error, dict):
        return None, None

    def bounded(value: object) -> str | None:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", value):
            return None
        return value

    return bounded(provider_error.get("type")), bounded(provider_error.get("code"))


class HostHTTPServer(ThreadingHTTPServer):
    coordinator: HandoffCoordinator
    settings: object | None
    capability_lease: str | None
    acknowledgement_candidate_root: Path
    acknowledgement_mode: str
    cached_acknowledgement_audio: bytes | None
    cached_acknowledgement_manifest: dict[str, object] | None
    cached_farewell_audio: bytes | None
    cached_farewell_manifest: dict[str, object] | None
    cached_acknowledgements: dict[str, tuple[bytes, dict[str, object]]]
    cached_farewells: dict[str, tuple[bytes, dict[str, object]]]
    session_expiry_warnings: dict[str, tuple[bytes, dict[str, object]]]
    app_language_path: Path | None
    startup_event: Callable[[str, int], None] | None


def build_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    real_microphone: bool = False,
    wake_after_arm: bool = False,
    acknowledgement_mode: str = "local",
    farewell_mode: str = "realtime",
    end_phrases: tuple[str, ...] = DEFAULT_REALTIME_END_PHRASES,
    tool_provider_config: object | None = None,
    tool_http_client: object | None = None,
    settings: object | None = None,
    capability_lease: str | None = None,
        acknowledgement_candidate_root: str | Path = "artifacts/audio/candidates/mandarin-ack",
    cached_acknowledgement_audio_path: str | Path | None = None,
    cached_acknowledgement_manifest_path: str | Path | None = None,
    cached_farewell_audio_path: str | Path | None = None,
    cached_farewell_manifest_path: str | Path | None = None,
    english_cached_acknowledgement_audio_path: str | Path | None = None,
    english_cached_acknowledgement_manifest_path: str | Path | None = None,
    english_cached_farewell_audio_path: str | Path | None = None,
    english_cached_farewell_manifest_path: str | Path | None = None,
    session_expiry_warning_en_path: str | Path | None = None,
    session_expiry_warning_zh_path: str | Path | None = None,
    app_language_path: str | Path | None = None,
    startup_event: Callable[[str, int], None] | None = None,
    negotiation_failure_sink: Callable[[dict[str, object]], None] | None = None,
) -> HostHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise HostServerError("Realtime host server must bind to loopback")
    cached_audio: bytes | None = None
    cached_manifest: dict[str, object] | None = None
    if acknowledgement_mode == "cached":
        if cached_acknowledgement_audio_path is None or cached_acknowledgement_manifest_path is None:
            raise HostServerError("Cached Realtime acknowledgement asset is not configured")
        try:
            cached_audio, cached_manifest = load_acknowledgement_asset(
                Path(cached_acknowledgement_audio_path),
                Path(cached_acknowledgement_manifest_path),
            )
        except RealtimeAckAssetError as exc:
            raise HostServerError(str(exc)) from exc
        if settings is not None and (
            cached_manifest.get("model") != settings.realtime_model
            or cached_manifest.get("voice") != settings.realtime_voice
        ):
            raise HostServerError("Cached Realtime acknowledgement model or voice does not match settings")
    cached_farewell_audio: bytes | None = None
    cached_farewell_manifest: dict[str, object] | None = None
    if farewell_mode == "cached":
        if cached_farewell_audio_path is None or cached_farewell_manifest_path is None:
            raise HostServerError("Cached Realtime farewell asset is not configured")
        try:
            cached_farewell_audio, cached_farewell_manifest = load_farewell_asset(
                Path(cached_farewell_audio_path),
                Path(cached_farewell_manifest_path),
            )
        except RealtimeFarewellAssetError as exc:
            raise HostServerError(str(exc)) from exc
        if settings is not None and (
            cached_farewell_manifest.get("voice") != settings.realtime_voice
            or cached_farewell_manifest.get("playback_gain") != settings.realtime_output_volume
        ):
            raise HostServerError("Cached Realtime farewell voice or gain does not match settings")
    english_paths = (
        english_cached_acknowledgement_audio_path,
        english_cached_acknowledgement_manifest_path,
        english_cached_farewell_audio_path,
        english_cached_farewell_manifest_path,
    )
    if any(path is not None for path in english_paths) and not all(path is not None for path in english_paths):
        raise HostServerError("All English cached voice cue assets must be configured together")
    english_ack: tuple[bytes, dict[str, object]] | None = None
    english_farewell: tuple[bytes, dict[str, object]] | None = None
    if all(path is not None for path in english_paths):
        english_ack_audio_path = Path(english_cached_acknowledgement_audio_path)
        english_ack_manifest_path = Path(english_cached_acknowledgement_manifest_path)
        english_farewell_audio_path = Path(english_cached_farewell_audio_path)
        english_farewell_manifest_path = Path(english_cached_farewell_manifest_path)
        if (
            english_ack_manifest_path != english_ack_audio_path.with_suffix(".json")
            or english_farewell_manifest_path != english_farewell_audio_path.with_suffix(".json")
        ):
            raise HostServerError("English cached voice cue manifests did not match their audio paths")
        try:
            english_ack = load_english_voice_cue(english_ack_audio_path, selected_required=True)
            english_farewell = load_english_voice_cue(english_farewell_audio_path, selected_required=True)
        except EnglishVoiceCueError as exc:
            raise HostServerError(str(exc)) from exc
        if english_ack[1].get("cue") != "ack" or english_farewell[1].get("cue") != "farewell":
            raise HostServerError("English cached voice cue types were invalid")
        if settings is not None and any(
            manifest.get("voice") != settings.realtime_voice
            or manifest.get("playback_gain") != settings.realtime_output_volume
            for _, manifest in (english_ack, english_farewell)
        ):
            raise HostServerError("English cached voice cue voice or gain does not match settings")
    language_path = Path(app_language_path) if app_language_path is not None else None
    warning_paths = {
        "en": session_expiry_warning_en_path,
        "zh-CN": session_expiry_warning_zh_path,
    }
    session_expiry_warnings: dict[str, tuple[bytes, dict[str, object]]] = {}
    if any(path is not None for path in warning_paths.values()):
        if not all(path is not None for path in warning_paths.values()):
            raise HostServerError("Both session expiry warning locales must be configured")
        try:
            for locale, path in warning_paths.items():
                session_expiry_warnings[locale] = load_session_expiry_cue(
                    Path(path), expected_slot=locale
                )
        except SessionExpiryCueError as exc:
            raise HostServerError(str(exc)) from exc
    lease = SoundDeviceWakeLease(open_microphone_stream) if real_microphone else MemoryWakeLease()
    server = HostHTTPServer((host, port), HostRequestHandler)
    server.coordinator = HandoffCoordinator(
        lease,
        open_wake_on_init=not wake_after_arm,
        acknowledgement_mode=acknowledgement_mode,
        farewell_mode=farewell_mode,
        end_phrases=end_phrases,
        tool_provider_config=tool_provider_config,
        tool_http_client=tool_http_client,
        app_language_provider=lambda: read_app_language(language_path),
        negotiation_failure_sink=negotiation_failure_sink,
    )
    server.settings = settings
    server.capability_lease = capability_lease
    server.acknowledgement_candidate_root = Path(acknowledgement_candidate_root)
    server.acknowledgement_mode = acknowledgement_mode
    server.farewell_mode = farewell_mode
    server.cached_acknowledgement_audio = cached_audio
    server.cached_acknowledgement_manifest = cached_manifest
    server.cached_farewell_audio = cached_farewell_audio
    server.cached_farewell_manifest = cached_farewell_manifest
    server.cached_acknowledgements = {}
    server.cached_farewells = {}
    server.session_expiry_warnings = session_expiry_warnings
    if isinstance(cached_audio, bytes) and isinstance(cached_manifest, dict):
        server.cached_acknowledgements["zh-CN"] = (cached_audio, cached_manifest)
    if isinstance(cached_farewell_audio, bytes) and isinstance(cached_farewell_manifest, dict):
        server.cached_farewells["zh-CN"] = (cached_farewell_audio, cached_farewell_manifest)
    if english_ack is not None and english_farewell is not None:
        server.cached_acknowledgements["en"] = english_ack
        server.cached_farewells["en"] = english_farewell
    server.app_language_path = language_path
    server.startup_event = startup_event
    return server


def resolve_static(path: str) -> tuple[bytes, str] | None:
    item = STATIC_FILES.get(path.split("?", 1)[0])
    if item is None:
        return None
    filename, content_type = item
    return (STATIC_ROOT / filename).read_bytes(), content_type


class HostRequestHandler(BaseHTTPRequestHandler):
    server: HostHTTPServer
    server_version = "HeyJarvisRealtimeHost/1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if self._handle_capability_bootstrap(parsed):
            return
        if not self._has_capability():
            self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
            return
        if parsed.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/api/command":
            try:
                after = int(urllib.parse.parse_qs(parsed.query).get("after", ["0"])[0])
            except ValueError:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_command_cursor"})
                return
            host_id = urllib.parse.parse_qs(parsed.query).get("host_id", [None])[0]
            if not isinstance(host_id, str):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "missing_host_identity"})
                return
            self._json(
                HTTPStatus.OK,
                {"command": self.server.coordinator.command_after(after, host_id=host_id)},
            )
            return
        if parsed.path == "/api/report":
            self._json(HTTPStatus.OK, self.server.coordinator.report())
            return
        if parsed.path == "/api/availability":
            self._json(
                HTTPStatus.OK,
                {"availability": self.server.coordinator.availability()},
            )
            return
        if parsed.path == "/api/app-language":
            self._json(
                HTTPStatus.OK,
                {
                    "app_language": read_app_language(getattr(self.server, "app_language_path", None)),
                    "app_theme": read_app_theme(getattr(self.server, "app_language_path", None)),
                },
            )
            return
        if parsed.path == "/api/realtime-settings":
            try:
                settings = self._settings(require_openai_api_key=False)
            except ConfigError as exc:
                self._json(HTTPStatus.CONFLICT, {"error": "host_control_failed", "message": str(exc)})
                return
            payload: dict[str, object] = {
                "model": settings.realtime_model,
                "voice": settings.realtime_voice,
                "output_volume": settings.realtime_output_volume,
                "input_noise_reduction": settings.realtime_input_noise_reduction,
            }
            host_server = getattr(self, "server", None)
            mode = getattr(host_server, "acknowledgement_mode", "local")
            manifest = getattr(host_server, "cached_acknowledgement_manifest", None)
            if mode == "cached" and isinstance(manifest, dict):
                payload["acknowledgement"] = {
                    "mode": "cached",
                    "url": "/acknowledgement.wav",
                    "duration_ms": manifest["duration_ms"],
                    "sha256": manifest["sha256"],
                }
            farewell_mode = getattr(host_server, "farewell_mode", "realtime")
            farewell_manifest = getattr(host_server, "cached_farewell_manifest", None)
            if farewell_mode == "cached" and isinstance(farewell_manifest, dict):
                payload["farewell"] = {
                    "mode": "cached",
                    "url": "/farewell.wav",
                    "duration_ms": farewell_manifest["duration_ms"],
                    "sha256": farewell_manifest["sha256"],
                }
            else:
                payload["farewell"] = {"mode": "realtime"}
            acknowledgement_assets = getattr(host_server, "cached_acknowledgements", {})
            farewell_assets = getattr(host_server, "cached_farewells", {})
            if mode == "cached" and farewell_mode == "cached":
                voice_cues: dict[str, object] = {}
                for locale in ("en", "zh-CN"):
                    acknowledgement_asset = acknowledgement_assets.get(locale)
                    farewell_asset = farewell_assets.get(locale)
                    if acknowledgement_asset is None or farewell_asset is None:
                        continue
                    acknowledgement_locale_manifest = acknowledgement_asset[1]
                    farewell_locale_manifest = farewell_asset[1]
                    encoded_locale = urllib.parse.quote(locale, safe="")
                    voice_cues[locale] = {
                        "acknowledgement": {
                            "mode": "cached",
                            "url": f"/acknowledgement.wav?locale={encoded_locale}",
                            "duration_ms": acknowledgement_locale_manifest["duration_ms"],
                            "sha256": acknowledgement_locale_manifest["sha256"],
                        },
                        "farewell": {
                            "mode": "cached",
                            "url": f"/farewell.wav?locale={encoded_locale}",
                            "duration_ms": farewell_locale_manifest["duration_ms"],
                            "sha256": farewell_locale_manifest["sha256"],
                        },
                    }
                if voice_cues:
                    payload["voice_cues"] = voice_cues
            warning_assets = getattr(host_server, "session_expiry_warnings", {})
            if set(warning_assets) == {"en", "zh-CN"}:
                payload["session_expiry_warnings"] = {
                    locale: {
                        "url": f"/session-expiry-warning.wav?locale={urllib.parse.quote(locale, safe='')}",
                        "duration_ms": warning_assets[locale][1]["duration_ms"],
                        "sha256": warning_assets[locale][1]["sha256"],
                    }
                    for locale in ("en", "zh-CN")
                }
            self._json(HTTPStatus.OK, payload)
            return
        if parsed.path == "/acknowledgement.wav":
            query = urllib.parse.parse_qs(parsed.query)
            if "locale" in query:
                locale = query["locale"][0]
                asset = getattr(self.server, "cached_acknowledgements", {}).get(locale)
                if locale not in {"en", "zh-CN"} or asset is None:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                    return
                self._bytes(HTTPStatus.OK, asset[0], "audio/wav")
                return
            body = getattr(self.server, "cached_acknowledgement_audio", None)
            if not isinstance(body, bytes):
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._bytes(HTTPStatus.OK, body, "audio/wav")
            return
        if parsed.path == "/farewell.wav":
            query = urllib.parse.parse_qs(parsed.query)
            if "locale" in query:
                locale = query["locale"][0]
                asset = getattr(self.server, "cached_farewells", {}).get(locale)
                if locale not in {"en", "zh-CN"} or asset is None:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                    return
                self._bytes(HTTPStatus.OK, asset[0], "audio/wav")
                return
            body = getattr(self.server, "cached_farewell_audio", None)
            if not isinstance(body, bytes):
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._bytes(HTTPStatus.OK, body, "audio/wav")
            return
        if parsed.path == "/session-expiry-warning.wav":
            query = urllib.parse.parse_qs(parsed.query)
            locale = query.get("locale", [""])[0]
            asset = getattr(self.server, "session_expiry_warnings", {}).get(locale)
            if locale not in {"en", "zh-CN"} or asset is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._bytes(HTTPStatus.OK, asset[0], "audio/wav")
            return
        asset = resolve_static(parsed.path)
        if asset is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        body, content_type = asset
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; media-src 'self' blob:; "
            "script-src 'self'; style-src 'self'",
        )
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if not self._has_capability():
            self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
            return
        try:
            if path == "/session":
                sdp = self._read_sdp()
                settings = self._settings(require_openai_api_key=True)
                assert settings.openai_api_key is not None
                answer = create_realtime_call(
                    api_key=settings.openai_api_key,
                    sdp=sdp,
                    session=build_realtime_session_config(settings),
                )
                self._bytes(HTTPStatus.OK, answer.encode("utf-8"), "application/sdp")
                return
            if path == "/api/simulate-wake":
                self._json(HTTPStatus.OK, {"session_id": self.server.coordinator.begin_handoff()})
                return
            if path == "/api/input-level-diagnostics":
                self.server.coordinator.request_input_level_diagnostics()
                self._json(HTTPStatus.OK, {"status": "armed_for_next_handoff"})
                return
            if path == "/api/acknowledgement-experiment":
                self.server.coordinator.request_realtime_acknowledgement_experiment()
                self._json(HTTPStatus.OK, {"status": "armed_for_next_handoff"})
                return
            if path == "/api/acknowledgement-capture/arm":
                payload = self._read_json(max_length=256)
                label = payload.get("label")
                if not isinstance(label, str):
                    raise HandoffError("Acknowledgement capture label was invalid")
                self.server.coordinator.request_realtime_acknowledgement_capture(label)
                self._json(HTTPStatus.OK, {"status": "armed_for_next_handoff", "candidate": label})
                return
            if path == "/api/acknowledgement-capture/candidate":
                payload = self._read_json(max_length=2_100_000)
                label = payload.get("label")
                transcript = payload.get("transcript")
                audio = payload.get("audio")
                if not isinstance(label, str) or not isinstance(audio, str):
                    raise HandoffError("Acknowledgement candidate payload was invalid")
                self.server.coordinator.validate_realtime_acknowledgement_capture(label)
                try:
                    wav_data = base64.b64decode(audio, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise HandoffError("Acknowledgement candidate audio was invalid") from exc
                settings = self._settings(require_openai_api_key=False)
                candidate = store_acknowledgement_candidate(
                    self.server.acknowledgement_candidate_root,
                    label=label,
                    wav_data=wav_data,
                    transcript=transcript,
                    model=settings.realtime_model,
                    voice=settings.realtime_voice,
                    output_gain=settings.realtime_output_volume,
                )
                self.server.coordinator.accept_realtime_acknowledgement_capture(label)
                self._json(
                    HTTPStatus.CREATED,
                    {
                        "status": "candidate_saved",
                        "candidate": label,
                        "duration_ms": candidate["duration_ms"],
                        "sha256": candidate["sha256"],
                    },
                )
                return
            if path == "/api/stop":
                self.server.coordinator.request_stop()
                self._json(HTTPStatus.OK, {"status": "stopping"})
                return
            if path == "/api/long-answer":
                self.server.coordinator.request_long_answer()
                self._json(HTTPStatus.OK, {"status": "requested"})
                return
            if path == "/api/fixture-audio":
                payload = self._read_json(max_length=800_000)
                name = payload.get("name")
                audio = payload.get("audio")
                if not isinstance(name, str) or not isinstance(audio, str):
                    raise HandoffError("Fixture audio payload was invalid")
                self.server.coordinator.request_fixture_audio(name, audio)
                self._json(HTTPStatus.OK, {"status": "requested"})
                return
            if path == "/api/event":
                payload = self._read_json()
                event_type = payload.pop("type", None)
                session_id = payload.pop("session_id", None)
                host_id = payload.pop("host_id", None)
                if (
                    not isinstance(event_type, str)
                    or not isinstance(host_id, str)
                    or (session_id is not None and not isinstance(session_id, str))
                ):
                    raise HandoffError("Host event payload was invalid")
                result = self.server.coordinator.host_event(
                    event_type,
                    session_id,
                    host_id=host_id,
                    **payload,
                )
                self._json(HTTPStatus.OK, {"status": result})
                return
            if path == "/api/startup-milestone":
                payload = self._read_json(max_length=256)
                stage = payload.get("stage")
                elapsed_ms = payload.get("elapsed_ms")
                if (
                    stage not in {"home_script_started", "home_first_paint", "home_interactive"}
                    or not isinstance(elapsed_ms, int)
                    or isinstance(elapsed_ms, bool)
                    or not 0 <= elapsed_ms <= 300_000
                ):
                    raise HandoffError("Startup milestone payload was invalid")
                if self.server.startup_event is not None:
                    self.server.startup_event(stage, elapsed_ms)
                self._json(HTTPStatus.OK, {"status": "recorded"})
                return
        except RealtimeCallError as exc:
            self._json(HTTPStatus.CONFLICT, exc.safe_payload())
            return
        except (ConfigError, HandoffError, HostServerError, RealtimeAckAssetError) as exc:
            self._json(HTTPStatus.CONFLICT, {"error": "host_control_failed", "message": str(exc)})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _settings(self, *, require_openai_api_key: bool) -> object:
        settings = getattr(getattr(self, "server", None), "settings", None)
        if settings is None:
            return load_settings(
                require_openai_api_key=require_openai_api_key,
                backend="realtime",
            )
        if require_openai_api_key and getattr(settings, "openai_api_key", None) is None:
            raise ConfigError(["OPENAI_API_KEY is required for Realtime"])
        return settings

    def _handle_capability_bootstrap(self, parsed: urllib.parse.ParseResult) -> bool:
        lease = getattr(getattr(self, "server", None), "capability_lease", None)
        if lease is None or parsed.path != "/" or not parsed.query:
            return False
        supplied = urllib.parse.parse_qs(parsed.query).get("lease", [""])[0]
        if supplied != lease:
            self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
            return True
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"hey_jarvis_lease={lease}; HttpOnly; SameSite=Lax; Path=/",
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return True

    def _has_capability(self) -> bool:
        lease = getattr(getattr(self, "server", None), "capability_lease", None)
        if lease is None:
            return True
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        value = cookie.get("hey_jarvis_lease")
        return value is not None and value.value == lease

    def _read_sdp(self) -> str:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/sdp":
            raise HostServerError("Realtime SDP content type was invalid")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise HostServerError("Realtime SDP size was invalid") from exc
        if length <= 0 or length > MAX_SDP_BYTES:
            raise HostServerError("Realtime SDP size was invalid")
        try:
            sdp = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HostServerError("Realtime SDP was invalid") from exc
        if not sdp.startswith("v=0"):
            raise HostServerError("Realtime SDP was invalid")
        return sdp

    def _read_json(self, *, max_length: int = 4096) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise HandoffError("Host event payload size was invalid") from exc
        if length <= 0 or length > max_length:
            raise HandoffError("Host event payload size was invalid")
        try:
            payload = json.loads(self.rfile.read(length).decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HandoffError("Host event payload was invalid") from exc
        if not isinstance(payload, dict):
            raise HandoffError("Host event payload was invalid")
        return payload

    def _json(self, status: HTTPStatus, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self._bytes(status, body, "application/json; charset=utf-8")

    def _bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/api/command":
            print(f"Realtime host: {self.command} {path}", file=sys.stderr)


def launch_chrome_app(url: str) -> None:
    if not CHROME_BINARY.is_file():
        raise HostServerError(f"Google Chrome app-mode host not found at {CHROME_BINARY}")
    subprocess.Popen([str(CHROME_BINARY), f"--app={url}"], close_fds=True)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip("'\"")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.realtime_host.server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--real-microphone", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        missing = [name for name, _ in STATIC_FILES.values() if not (STATIC_ROOT / name).is_file()]
        print("Realtime host ready" if not missing else "Realtime host assets missing: " + ", ".join(missing))
        return 0 if not missing else 1
    try:
        server = build_server(args.host, args.port, real_microphone=args.real_microphone)
        url = f"http://{args.host}:{server.server_port}/"
        if args.launch:
            launch_chrome_app(url)
        print(f"Realtime Chrome app-mode host: {url}")
        print("After Arm, trigger a hands-free cycle with: curl -X POST " + url + "api/simulate-wake")
        server.serve_forever()
    except (HostServerError, HandoffError) as exc:
        print(f"Realtime host startup error: {exc}")
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if "server" in locals():
            server.coordinator.close()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

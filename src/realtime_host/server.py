"""Loopback control server for the development Chrome app-mode WebRTC host."""

from __future__ import annotations

import argparse
import json
import os
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
from src.realtime_host.coordinator import HandoffCoordinator, HandoffError, SoundDeviceWakeLease
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
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class HostServerError(RuntimeError):
    pass


class MemoryWakeLease:
    """Dependency-free default lease; --real-microphone exercises sounddevice ownership."""

    def __init__(self) -> None:
        self.is_open = False

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False


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
            "- If the user clearly and unambiguously wants to end the current conversation, call end_conversation with {} and do not provide a spoken or substantive response.",
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
        raise HostServerError(f"OpenAI Realtime call failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise HostServerError("OpenAI Realtime call failed safely") from exc
    if not answer.startswith("v=0") or len(answer.encode("utf-8")) > MAX_SDP_BYTES:
        raise HostServerError("OpenAI Realtime SDP answer was malformed")
    return answer


class HostHTTPServer(ThreadingHTTPServer):
    coordinator: HandoffCoordinator
    settings: object | None
    capability_lease: str | None


def build_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    real_microphone: bool = False,
    wake_after_arm: bool = False,
    end_phrases: tuple[str, ...] = DEFAULT_REALTIME_END_PHRASES,
    tool_provider_config: object | None = None,
    tool_http_client: object | None = None,
    settings: object | None = None,
    capability_lease: str | None = None,
) -> HostHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise HostServerError("Realtime host server must bind to loopback")
    lease = SoundDeviceWakeLease(open_microphone_stream) if real_microphone else MemoryWakeLease()
    server = HostHTTPServer((host, port), HostRequestHandler)
    server.coordinator = HandoffCoordinator(
        lease,
        open_wake_on_init=not wake_after_arm,
        end_phrases=end_phrases,
        tool_provider_config=tool_provider_config,
        tool_http_client=tool_http_client,
    )
    server.settings = settings
    server.capability_lease = capability_lease
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
        if parsed.path == "/api/realtime-settings":
            try:
                settings = self._settings(require_openai_api_key=False)
            except ConfigError as exc:
                self._json(HTTPStatus.CONFLICT, {"error": "host_control_failed", "message": str(exc)})
                return
            self._json(
                HTTPStatus.OK,
                {
                    "output_volume": settings.realtime_output_volume,
                    "input_noise_reduction": settings.realtime_input_noise_reduction,
                },
            )
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
        except (ConfigError, HandoffError, HostServerError) as exc:
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
            f"hey_jarvis_lease={lease}; HttpOnly; SameSite=Strict; Path=/",
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

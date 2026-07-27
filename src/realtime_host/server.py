"""Loopback control server for the development Chrome app-mode WebRTC host."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Mapping

from src.audio_input import open_microphone_stream
from src.config import ConfigError, DEFAULT_REALTIME_END_PHRASES, load_settings
from src.realtime_host.coordinator import HandoffCoordinator, HandoffError, SoundDeviceWakeLease


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8770
DEFAULT_MODEL = "gpt-realtime-2.1"
DEFAULT_VOICE = "marin"
CLIENT_SECRET_URL = "https://api.openai.com/v1/realtime/client_secrets"
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


def mint_client_secret(*, api_key: str, model: str, voice: str, urlopen: Callable[..., object] = urllib.request.urlopen) -> dict[str, object]:
    request = urllib.request.Request(
        CLIENT_SECRET_URL,
        data=json.dumps({"session": {"type": "realtime", "model": model, "audio": {"output": {"voice": voice}}}}).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise HostServerError(f"OpenAI client-secret request failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HostServerError("OpenAI client-secret request failed safely") from exc
    value = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(value, str) or not value:
        raise HostServerError("OpenAI client-secret response was malformed")
    return {"value": value, "model": model, "voice": voice}


class HostHTTPServer(ThreadingHTTPServer):
    coordinator: HandoffCoordinator


def build_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    real_microphone: bool = False,
    wake_after_arm: bool = False,
    end_phrases: tuple[str, ...] = DEFAULT_REALTIME_END_PHRASES,
) -> HostHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise HostServerError("Realtime host server must bind to loopback")
    lease = SoundDeviceWakeLease(open_microphone_stream) if real_microphone else MemoryWakeLease()
    server = HostHTTPServer((host, port), HostRequestHandler)
    server.coordinator = HandoffCoordinator(
        lease,
        open_wake_on_init=not wake_after_arm,
        end_phrases=end_phrases,
    )
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
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            if path == "/token":
                settings = load_settings(require_openai_api_key=True, backend="realtime")
                assert settings.openai_api_key is not None
                token = mint_client_secret(
                    api_key=settings.openai_api_key,
                    model=settings.realtime_model,
                    voice=settings.realtime_voice,
                )
                token["session"] = {
                    "model": settings.realtime_model,
                    "voice": settings.realtime_voice,
                    "output_volume": settings.realtime_output_volume,
                    "server_vad": settings.realtime_server_vad_enabled,
                    "server_vad_threshold": settings.realtime_server_vad_threshold,
                    "input_noise_reduction": settings.realtime_input_noise_reduction,
                    "input_transcription": settings.realtime_input_transcription_enabled,
                    "transcription_model": settings.transcribe_model,
                }
                self._json(HTTPStatus.OK, token)
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
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/api/command":
            print(f"Realtime host: {self.command} {path}")


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

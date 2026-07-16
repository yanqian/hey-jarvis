"""Loopback server for the Realtime WebRTC full-duplex validation probe."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Mapping


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MODEL = "gpt-realtime-2.1"
DEFAULT_VOICE = "marin"
CLIENT_SECRET_URL = "https://api.openai.com/v1/realtime/client_secrets"
STATIC_ROOT = Path(__file__).resolve().parent
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class ProbeError(RuntimeError):
    """A safe operator-facing probe error."""


def load_probe_config(
    env: Mapping[str, str] | None = None,
    *,
    env_file: str | Path = ".env",
) -> tuple[str, str, str]:
    """Return API key, model, and voice without exposing the key."""

    values = _read_env_file(Path(env_file))
    values.update(os.environ if env is None else env)
    api_key = values.get("OPENAI_API_KEY", "").strip().strip("'\"")
    if not api_key or api_key in {"your_api_key_here", "replace_me", "changeme"}:
        raise ProbeError("OPENAI_API_KEY is required in .env or the environment")
    model = values.get("REALTIME_PROBE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    voice = values.get("REALTIME_PROBE_VOICE", DEFAULT_VOICE).strip() or DEFAULT_VOICE
    return api_key, model, voice


def mint_client_secret(
    *,
    api_key: str,
    model: str,
    voice: str,
    urlopen: Callable[..., object] = urllib.request.urlopen,
) -> dict[str, object]:
    """Mint a browser-safe ephemeral Realtime client secret."""

    payload = {
        "session": {
            "type": "realtime",
            "model": model,
            "audio": {"output": {"voice": voice}},
        }
    }
    request = urllib.request.Request(
        CLIENT_SECRET_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ProbeError(f"OpenAI client-secret request failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProbeError("OpenAI client-secret request could not connect") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError("OpenAI client-secret response was malformed") from exc

    value = data.get("value") if isinstance(data, dict) else None
    if not isinstance(value, str) or not value:
        raise ProbeError("OpenAI client-secret response did not contain an ephemeral value")
    result: dict[str, object] = {"value": value, "model": model, "voice": voice}
    if isinstance(data.get("expires_at"), int):
        result["expires_at"] = data["expires_at"]
    return result


def build_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Build the loopback HTTP server without starting it."""

    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ProbeError("The validation server must bind to a loopback address")
    return ThreadingHTTPServer((host, port), ProbeRequestHandler)


def resolve_static_asset(path: str) -> tuple[bytes, str] | None:
    """Resolve a safe static route without accepting filesystem paths."""

    route = path.split("?", 1)[0]
    static = STATIC_FILES.get(route)
    if static is None:
        return None
    filename, content_type = static
    return (STATIC_ROOT / filename).read_bytes(), content_type


class ProbeRequestHandler(BaseHTTPRequestHandler):
    server_version = "HeyJarvisRealtimeProbe/1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        static = resolve_static_asset(path)
        if static is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        body, content_type = static
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        path = self.path.split("?", 1)[0]
        if path != "/token":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            api_key, model, voice = load_probe_config()
            result = mint_client_secret(api_key=api_key, model=model, voice=voice)
        except ProbeError as exc:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"error": "client_secret_unavailable", "message": str(exc)},
            )
            return
        self._send_json(HTTPStatus.OK, result)

    def log_message(self, format: str, *args: object) -> None:
        safe_path = self.path.split("?", 1)[0]
        print(f"Realtime probe: {self.command} {safe_path} -> {args[1] if len(args) > 1 else '-'}")

    def _send_json(self, status: HTTPStatus, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def check_probe() -> int:
    missing = [name for name, _ in STATIC_FILES.values() if not (STATIC_ROOT / name).is_file()]
    if missing:
        print("Probe assets missing: " + ", ".join(sorted(set(missing))))
        return 1
    try:
        _, model, voice = load_probe_config()
    except ProbeError as exc:
        print(f"Probe configuration error: {exc}")
        return 1
    print(f"Realtime WebRTC probe ready: model={model} voice={voice} key=configured")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m spikes.realtime_webrtc.server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check:
        return check_probe()
    try:
        server = build_server(args.host, args.port)
    except ProbeError as exc:
        print(f"Probe startup error: {exc}")
        return 1
    print(f"Realtime WebRTC probe: http://{args.host}:{server.server_port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Realtime WebRTC probe")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

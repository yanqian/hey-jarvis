#!/usr/bin/env python3
"""Isolated loopback service for the F086 Tauri/WKWebView capability spike."""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Mapping


HOST = "127.0.0.1"
DEFAULT_PORT = 8871
MAX_SDP_BYTES = 100_000
MAX_JSON_BYTES = 8_192
REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
ALLOWED_EVENTS = {
    "microphone_requested",
    "microphone_acquired",
    "transport_connected",
    "session_created",
    "speech_started",
    "speech_stopped",
    "response_created",
    "response_done",
    "playback_started",
    "playback_stopped",
    "media_released",
    "reacquire_result",
    "error",
}
SAFE_DETAIL_KEYS = {
    "echoCancellation",
    "echoCancellationRequested",
    "echoCancellationAllSupported",
    "noiseSuppression",
    "autoGainControl",
    "sampleRate",
    "channelCount",
    "during_playback",
    "status",
    "reason",
    "ok",
}


class ProbeError(RuntimeError):
    """A bounded user-facing capability-spike failure."""


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key.replace("_", "").isalnum():
            values[key] = value
    return values


def load_probe_config(env: Mapping[str, str] | None = None) -> dict[str, object]:
    active = dict(os.environ if env is None else env)
    env_path = Path(active.get("TAURI_SPIKE_ENV_FILE", ".env"))
    file_values = load_env_file(env_path)
    token = active.get("TAURI_SPIKE_TOKEN", "")
    if len(token) < 32:
        raise ProbeError("TAURI_SPIKE_TOKEN is missing or too short")
    try:
        port = int(active.get("TAURI_SPIKE_PORT", str(DEFAULT_PORT)))
    except ValueError as exc:
        raise ProbeError("TAURI_SPIKE_PORT is invalid") from exc
    if not 1024 <= port <= 65535:
        raise ProbeError("TAURI_SPIKE_PORT is outside the allowed range")
    return {
        "token": token,
        "port": port,
        "api_key": active.get("OPENAI_API_KEY") or file_values.get("OPENAI_API_KEY"),
        "model": file_values.get("REALTIME_MODEL", "gpt-realtime-2.1"),
        "voice": file_values.get("REALTIME_VOICE", "alloy"),
    }


def build_session_config(config: Mapping[str, object]) -> dict[str, object]:
    return {
        "type": "realtime",
        "model": config["model"],
        "instructions": (
            "You are the isolated Hey Jarvis Tauri capability probe. "
            "Reply concisely in the user's language. Support natural interruption."
        ),
        "output_modalities": ["audio"],
        "audio": {
            "input": {
                "noise_reduction": {"type": "far_field"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.8,
                    "create_response": True,
                    "interrupt_response": True,
                },
            },
            "output": {"voice": config["voice"]},
        },
    }


def multipart_call_body(
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
            json.dumps(session, separators=(",", ":")).encode("utf-8"),
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
) -> str:
    if not api_key:
        raise ProbeError("OPENAI_API_KEY is not configured in the spike .env")
    if not sdp.startswith("v=0") or len(sdp.encode("utf-8")) > MAX_SDP_BYTES:
        raise ProbeError("Realtime SDP offer is invalid")
    boundary = f"tauri-spike-{uuid.uuid4().hex}"
    request = urllib.request.Request(
        REALTIME_CALLS_URL,
        data=multipart_call_body(sdp, session, boundary=boundary),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            answer = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ProbeError(f"OpenAI Realtime call failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise ProbeError("OpenAI Realtime call failed safely") from exc
    if not answer.startswith("v=0") or len(answer.encode("utf-8")) > MAX_SDP_BYTES:
        raise ProbeError("OpenAI Realtime SDP answer is invalid")
    return answer


def sanitize_event(payload: Mapping[str, object]) -> dict[str, object]:
    event_type = payload.get("type")
    if event_type not in ALLOWED_EVENTS:
        raise ProbeError("Event type is not allowlisted")
    sanitized: dict[str, object] = {"type": event_type}
    for key in SAFE_DETAIL_KEYS:
        value = payload.get(key)
        if isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if abs(float(value)) <= 192_000:
                sanitized[key] = value
        elif isinstance(value, str) and 0 < len(value) <= 100:
            if all(char.isalnum() or char in "_.:-" for char in value):
                sanitized[key] = value
    return sanitized


def reacquire_microphone(
    sounddevice_module: object | None = None,
    *,
    timeout: float = 2.0,
) -> dict[str, object]:
    try:
        sounddevice = sounddevice_module
        if sounddevice is None:
            import sounddevice as sounddevice_import

            sounddevice = sounddevice_import
        received = threading.Event()
        capture = {"frames": 0, "overflowed": False}

        def callback(
            data: object,
            frames: int,
            _time_info: object,
            status: object,
        ) -> None:
            capture["frames"] = min(int(frames), len(bytes(data)) // 2)
            capture["overflowed"] = bool(status)
            received.set()

        stream = sounddevice.RawInputStream(
            samplerate=16_000,
            channels=1,
            dtype="int16",
            blocksize=1_280,
            callback=callback,
        )
        stream.start()
        captured = received.wait(timeout)
        stream.stop()
        stream.close()
        if not captured:
            return {
                "ok": False,
                "frames": 0,
                "overflowed": False,
                "reason": "microphone_timeout",
            }
        return {
            "ok": True,
            "frames": capture["frames"],
            "overflowed": capture["overflowed"],
            "reason": "reacquired",
        }
    except Exception:
        return {"ok": False, "frames": 0, "overflowed": False, "reason": "microphone_unavailable"}


class ProbeState:
    def __init__(self, config: Mapping[str, object]) -> None:
        self.config = dict(config)
        self.events: list[dict[str, object]] = []
        self.lock = threading.Lock()

    def record(self, event: Mapping[str, object]) -> None:
        sanitized = sanitize_event(event)
        with self.lock:
            self.events.append(sanitized)
            self.events = self.events[-100:]

    def report(self) -> dict[str, object]:
        with self.lock:
            events = list(self.events)
        event_types = [str(event["type"]) for event in events]
        return {
            "schema_version": 1,
            "host": "tauri-wkwebview",
            "events": events,
            "event_count": len(events),
            "media_released": "media_released" in event_types,
            "reacquired": any(
                event.get("type") == "reacquire_result" and event.get("ok") is True
                for event in events
            ),
        }


class ProbeServer(ThreadingHTTPServer):
    state: ProbeState


class ProbeHandler(BaseHTTPRequestHandler):
    server: ProbeServer
    server_version = "HeyJarvisTauriSpike/1"

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Probe-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-Probe-Token", "")
        expected = str(self.server.state.config["token"])
        return secrets.compare_digest(supplied, expected)

    def _bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: Mapping[str, object]) -> None:
        self._bytes(
            status,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            "application/json",
        )

    def _read(self, maximum: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ProbeError("Request body size is invalid") from exc
        if length <= 0 or length > maximum:
            raise ProbeError("Request body size is invalid")
        return self.rfile.read(length)

    def _read_json(self) -> dict[str, object]:
        try:
            payload = json.loads(self._read(MAX_JSON_BYTES))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProbeError("JSON body is invalid") from exc
        if not isinstance(payload, dict):
            raise ProbeError("JSON body must be an object")
        return payload

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        if self.path == "/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "openai_configured": bool(self.server.state.config.get("api_key")),
                },
            )
            return
        if self.path == "/report":
            self._json(HTTPStatus.OK, self.server.state.report())
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        try:
            if self.path == "/session":
                if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/sdp":
                    raise ProbeError("Session request must use application/sdp")
                offer = self._read(MAX_SDP_BYTES).decode("utf-8")
                answer = create_realtime_call(
                    api_key=str(self.server.state.config.get("api_key") or ""),
                    sdp=offer,
                    session=build_session_config(self.server.state.config),
                )
                self._bytes(HTTPStatus.OK, answer.encode("utf-8"), "application/sdp")
                return
            if self.path == "/event":
                self.server.state.record(self._read_json())
                self._json(HTTPStatus.OK, {"status": "recorded"})
                return
            if self.path == "/reacquire":
                self._read_json()
                result = reacquire_microphone()
                self._json(HTTPStatus.OK, result)
                return
        except (ProbeError, UnicodeDecodeError) as exc:
            self._json(HTTPStatus.CONFLICT, {"error": "probe_failed", "message": str(exc)})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format: str, *args: object) -> None:
        return


def build_server(config: Mapping[str, object]) -> ProbeServer:
    server = ProbeServer((HOST, int(config["port"])), ProbeHandler)
    server.state = ProbeState(config)
    return server


def monitor_parent(
    server: ProbeServer,
    parent_pid: int,
    *,
    getppid: Callable[[], int] = os.getppid,
    wait: Callable[[float], None] = time.sleep,
    interval: float = 0.25,
) -> None:
    """Stop the sidecar when its supervising Tauri process disappears."""
    while getppid() == parent_pid:
        wait(interval)
    server.shutdown()


def main() -> int:
    try:
        config = load_probe_config()
        server = build_server(config)
    except (OSError, ProbeError) as exc:
        print(f"TAURI_SPIKE_ERROR {type(exc).__name__}", file=sys.stderr, flush=True)
        return 1
    parent_pid = os.getppid()
    threading.Thread(
        target=monitor_parent,
        args=(server, parent_pid),
        daemon=True,
        name="tauri-parent-monitor",
    ).start()
    print(f"TAURI_SPIKE_READY port={server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Product sidecar entrypoint for the Tauri/WKWebView runtime."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO
from urllib.parse import quote


SIDECAR_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SIDECAR_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    # Development uses source by path, never cwd. F090 replaces this script
    # launch with a bundled executable containing the same project modules.
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SIDECAR_DIR) not in sys.path:
    sys.path.insert(0, str(SIDECAR_DIR))

from fake_sidecar import PROTOCOL_VERSION, ProtocolError, _write, parse_message  # noqa: E402
from src.config import load_settings, wake_acknowledgement_missing_message  # noqa: E402
from src.main import _build_wake_detector  # noqa: E402
from src.player import MacOSPlayer  # noqa: E402
from src.realtime.controller import RealtimeSessionController  # noqa: E402
from src.realtime_host.server import build_server  # noqa: E402
from src.tools.providers import provider_config_from_settings  # noqa: E402


LOGGER = logging.getLogger("hey_jarvis.mac_sidecar")
ACKNOWLEDGEMENT_RESOURCE = Path("assets/wake_acknowledgement_alloy.mp3")


class ProductRuntimeError(RuntimeError):
    pass


class ProductRuntime:
    def __init__(
        self,
        *,
        server: object,
        detector: object,
        controller_thread: threading.Thread,
        stop_event: threading.Event,
        control_url: str,
    ) -> None:
        self.server = server
        self.detector = detector
        self.controller_thread = controller_thread
        self.stop_event = stop_event
        self.control_url = control_url

    @classmethod
    def start(
        cls,
        *,
        session_id: str,
        resource_dir: Path,
        app_support_dir: Path,
        env: Mapping[str, str] | None = None,
    ) -> "ProductRuntime":
        del app_support_dir  # Reserved for app-owned logs/settings in F089/F091.
        values = os.environ if env is None else env
        settings = load_settings(
            env=values,
            env_file=None,
            require_openai_api_key=True,
            backend="realtime",
        )
        acknowledgement = (resource_dir / ACKNOWLEDGEMENT_RESOURCE).resolve()
        settings = replace(
            settings,
            wake_acknowledgement_audio_path=acknowledgement,
            realtime_bridge_host="127.0.0.1",
            realtime_bridge_port=0,
        )
        missing = wake_acknowledgement_missing_message(settings)
        if settings.realtime_acknowledgement_mode == "local" and missing is not None:
            raise ProductRuntimeError(missing)

        detector = _build_wake_detector(settings, logger=LOGGER)
        if hasattr(detector, "preload"):
            detector.preload()
        server = build_server(
            "127.0.0.1",
            0,
            real_microphone=True,
            wake_after_arm=True,
            end_phrases=settings.realtime_end_phrases,
            tool_provider_config=provider_config_from_settings(settings),
            settings=settings,
            capability_lease=session_id,
        )
        server_thread = threading.Thread(
            target=server.serve_forever,
            name="hey-jarvis-loopback",
            daemon=True,
        )
        server_thread.start()

        player = MacOSPlayer(logger=LOGGER)
        acknowledgement_duration_ms = (
            player.duration_ms(settings.wake_acknowledgement_audio_path)
            if settings.realtime_acknowledgement_mode == "local"
            else None
        )

        def play_acknowledgement() -> None:
            if settings.realtime_acknowledgement_mode == "local":
                player.play_acknowledgement(settings.wake_acknowledgement_audio_path)

        controller = RealtimeSessionController(
            coordinator=server.coordinator,
            wake_detector=detector,
            play_acknowledgement=play_acknowledgement,
            acknowledgement_duration_ms=acknowledgement_duration_ms,
            idle_timeout_seconds=settings.realtime_idle_timeout_seconds,
            max_duration_seconds=settings.realtime_max_duration_seconds,
            wake_confirmation_frames=settings.wake_confirmation_frames,
        )
        stop_event = threading.Event()

        def run_controller() -> None:
            while not stop_event.is_set():
                result = controller.run_once()
                LOGGER.info(
                    "session ended reason=%s recovered_to_wake=%s",
                    result.reason,
                    str(result.recovered_to_wake).lower(),
                )
                if not result.recovered_to_wake:
                    break

        controller_thread = threading.Thread(
            target=run_controller,
            name="hey-jarvis-controller",
            daemon=True,
        )
        controller_thread.start()
        control_url = (
            f"http://127.0.0.1:{server.server_port}/"
            f"?lease={quote(session_id, safe='')}"
        )
        return cls(
            server=server,
            detector=detector,
            controller_thread=controller_thread,
            stop_event=stop_event,
            control_url=control_url,
        )

    def close(self) -> None:
        self.stop_event.set()
        self.server.shutdown()
        self.server.server_close()
        self.server.coordinator.close()
        close = getattr(self.detector, "close", None)
        if close is not None:
            close()


RuntimeFactory = Callable[..., ProductRuntime]


def run(
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
    *,
    runtime_factory: RuntimeFactory = ProductRuntime.start,
    env: Mapping[str, str] | None = None,
) -> int:
    session_id: str | None = None
    inbound_sequence = 0
    outbound_sequence = 1
    runtime: ProductRuntime | None = None

    try:
        for line in input_stream:
            try:
                message = parse_message(
                    line.rstrip("\n"),
                    expected_session=session_id,
                    last_sequence=inbound_sequence,
                )
            except ProtocolError:
                return 2
            inbound_sequence = message["sequence"]
            payload = message["payload"]

            if session_id is None:
                if payload["kind"] != "startup":
                    return 2
                session_id = message["session_id"]
                try:
                    runtime = runtime_factory(
                        session_id=session_id,
                        resource_dir=Path(payload["resource_dir"]),
                        app_support_dir=Path(payload["app_support_dir"]),
                        env=os.environ if env is None else env,
                    )
                except Exception as exc:
                    LOGGER.error("product runtime startup failed: %s", type(exc).__name__)
                    _write(
                        output_stream,
                        session_id,
                        outbound_sequence,
                        {
                            "kind": "error",
                            "code": f"startup_{type(exc).__name__}",
                            "recoverable": False,
                        },
                    )
                    return 1
                _write(
                    output_stream,
                    session_id,
                    outbound_sequence,
                    {
                        "kind": "ready",
                        "sidecar_version": "0.2.0-product",
                        "capabilities": [
                            "wake",
                            "realtime",
                            "tools",
                            "health",
                            "shutdown",
                        ],
                        "control_url": runtime.control_url,
                    },
                )
                outbound_sequence += 1
                continue

            kind = payload["kind"]
            if kind == "lifecycle" and payload["event"] == "health_check":
                _write(
                    output_stream,
                    session_id,
                    outbound_sequence,
                    {
                        "kind": "lifecycle",
                        "event": "healthy",
                        "detail": "product runtime",
                    },
                )
                outbound_sequence += 1
            elif kind == "settings":
                _write(
                    output_stream,
                    session_id,
                    outbound_sequence,
                    {
                        "kind": "lifecycle",
                        "event": "settings_applied",
                        "detail": None,
                    },
                )
                outbound_sequence += 1
            elif kind == "session":
                _write(
                    output_stream,
                    session_id,
                    outbound_sequence,
                    {
                        "kind": "lifecycle",
                        "event": "session_observed",
                        "detail": payload["action"],
                    },
                )
                outbound_sequence += 1
            elif kind == "shutdown":
                _write(
                    output_stream,
                    session_id,
                    outbound_sequence,
                    {
                        "kind": "lifecycle",
                        "event": "stopping",
                        "detail": payload["reason"],
                    },
                )
                return 0
            else:
                return 2
    finally:
        if runtime is not None:
            runtime.close()

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    raise SystemExit(run())

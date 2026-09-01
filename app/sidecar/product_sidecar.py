#!/usr/bin/env python3
"""Product sidecar entrypoint for the Tauri/WKWebView runtime."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import threading
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO
from urllib.parse import quote


PROCESS_STARTED = time.monotonic()


SIDECAR_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SIDECAR_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    # Development uses source by path, never cwd. F090 replaces this script
    # launch with a bundled executable containing the same project modules.
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SIDECAR_DIR) not in sys.path:
    sys.path.insert(0, str(SIDECAR_DIR))

from fake_sidecar import PROTOCOL_VERSION, ProtocolError, _write, parse_message  # noqa: E402
from src.config import Settings, load_settings, wake_acknowledgement_missing_message  # noqa: E402
from src.main import _build_wake_detector  # noqa: E402
from src.player import MacOSPlayer  # noqa: E402
from src.realtime.controller import RealtimeSessionController  # noqa: E402
from src.realtime_host.server import build_server  # noqa: E402
from src.tools.providers import provider_config_from_settings  # noqa: E402
from src.wake_diagnostics import (  # noqa: E402
    AppWakePreferences,
    WakeDiagnostics,
    load_app_wake_preferences,
)


LOGGER = logging.getLogger("hey_jarvis.mac_sidecar")
ACKNOWLEDGEMENT_RESOURCE = Path("assets/wake_acknowledgement_alloy.mp3")
CACHED_ACKNOWLEDGEMENT_RESOURCE = Path("assets/realtime_acknowledgement_alloy_zh.wav")
CACHED_ACKNOWLEDGEMENT_MANIFEST_RESOURCE = Path("assets/realtime_acknowledgement_alloy_zh.json")
CACHED_FAREWELL_RESOURCE = Path("assets/realtime_farewell_alloy_zh.wav")
CACHED_FAREWELL_MANIFEST_RESOURCE = Path("assets/realtime_farewell_alloy_zh.json")
ENGLISH_CACHED_ACKNOWLEDGEMENT_RESOURCE = Path("assets/realtime_acknowledgement_alloy_en.wav")
ENGLISH_CACHED_ACKNOWLEDGEMENT_MANIFEST_RESOURCE = Path("assets/realtime_acknowledgement_alloy_en.json")
ENGLISH_CACHED_FAREWELL_RESOURCE = Path("assets/realtime_farewell_alloy_en.wav")
ENGLISH_CACHED_FAREWELL_MANIFEST_RESOURCE = Path("assets/realtime_farewell_alloy_en.json")
SESSION_EXPIRY_WARNING_EN_RESOURCE = Path("assets/session_expiry_warning_alloy_en.wav")
SESSION_EXPIRY_WARNING_ZH_RESOURCE = Path("assets/session_expiry_warning_alloy_zh.wav")
READY_CHIME_RESOURCE = Path("assets/realtime_ready_chime.wav")
PRIVATE_BOOTSTRAP_MAX_BYTES = 4096
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
DIAGNOSTIC_LIMIT_BYTES = 512 * 1024
DIAGNOSTIC_GENERATIONS = 3
CONTROLLER_SHUTDOWN_TIMEOUT_SECONDS = 4.0
SAFE_DIAGNOSTIC = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
SAFE_REALTIME_DIAGNOSTIC = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
FORBIDDEN_DIAGNOSTIC = ("sk-", "api_key", "authorization", "sdp", "candidate", "transcript", "answer", "tool_argument", "provider_body", "audio")


class ProductRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def safe_realtime_diagnostic_identifier(value: object) -> bool:
    if not isinstance(value, str) or not SAFE_REALTIME_DIAGNOSTIC.fullmatch(value):
        return False
    lowered = value.lower()
    return not lowered.startswith("sk-") and not lowered.startswith("ek_")


def apply_app_wake_preferences(
    settings: Settings,
    preferences_path: Path,
) -> tuple[Settings, AppWakePreferences]:
    """Apply the native bounded wake experiment before detector/controller construction."""

    try:
        app_preferences = load_app_wake_preferences(preferences_path)
    except ValueError as exc:
        raise ProductRuntimeError("preferences_corrupt") from exc
    return (
        replace(
            settings,
            wake_threshold=app_preferences.threshold,
            wake_confirmation_frames=app_preferences.confirmation_frames,
        ),
        app_preferences,
    )


def build_app_realtime_wake_options(
    settings: Settings,
    app_wake_preferences: AppWakePreferences,
    app_support_dir: Path,
) -> dict[str, object]:
    """Build the app-side controller inputs using the shared wake writer."""

    return {
        "wake_threshold": settings.wake_threshold,
        "wake_confirmation_frames": settings.wake_confirmation_frames,
        "wake_diagnostics": (
            WakeDiagnostics(app_support_dir)
            if app_wake_preferences.diagnostics_enabled
            else None
        ),
    }


def app_runtime_configuration_env(env: Mapping[str, str]) -> dict[str, str]:
    """Keep CLI-only wake controls from overriding native app preferences."""

    values = dict(env)
    for cli_only_key in (
        "WAKE_THRESHOLD",
        "WAKE_CONFIRMATION_FRAMES",
        "WAKE_DIAGNOSTICS_ENABLED",
        "WAKE_DIAGNOSTICS_DIR",
    ):
        values.pop(cli_only_key, None)
    return values


class LifecycleDiagnostics:
    """Bounded lifecycle-only JSONL; arbitrary values never enter diagnostics."""

    def __init__(self, app_support_dir: Path, session_id: str) -> None:
        self.root = app_support_dir / "diagnostics"
        self.path = self.root / "python.jsonl"
        self.realtime_path = self.root / "realtime.jsonl"
        self.session_id = session_id if SAFE_DIAGNOSTIC.fullmatch(session_id) else None
        self._lock = threading.Lock()

    def record(self, event: str, state: str | None = None) -> None:
        if not SAFE_DIAGNOSTIC.fullmatch(event) or (
            state is not None and not SAFE_DIAGNOSTIC.fullmatch(state)
        ):
            return
        if any(marker in event.lower() or (state is not None and marker in state.lower()) for marker in FORBIDDEN_DIAGNOSTIC):
            return
        record = {
            "schema": 1,
            "at_ms": int(time.time() * 1000),
            "component": "python",
            "event": event,
            "session": self.session_id,
            "state": state,
        }
        self._append(self.path, record)

    def record_negotiation_failure(self, detail: dict[str, object]) -> None:
        allowed = {
            "reason",
            "localHttpStatus",
            "upstreamHttpStatus",
            "errorType",
            "errorCode",
        }
        if set(detail) - allowed or detail.get("reason") != "webrtc_negotiation_failed":
            return
        local_status = detail.get("localHttpStatus")
        if (
            isinstance(local_status, bool)
            or not isinstance(local_status, int)
            or not 400 <= local_status <= 599
        ):
            return
        record: dict[str, object] = {
            "schema": "hey-jarvis-realtime-v1",
            "at_ms": int(time.time() * 1000),
            "component": "python",
            "event": "realtime_negotiation_failed",
            "session": self.session_id,
            "local_http_status": local_status,
        }
        upstream_status = detail.get("upstreamHttpStatus")
        if upstream_status is not None:
            if (
                isinstance(upstream_status, bool)
                or not isinstance(upstream_status, int)
                or not 400 <= upstream_status <= 599
            ):
                return
            record["upstream_http_status"] = upstream_status
        for source, target in (("errorType", "error_type"), ("errorCode", "error_code")):
            value = detail.get(source)
            if value is not None:
                if not safe_realtime_diagnostic_identifier(value):
                    return
                record[target] = value
        self._append(self.realtime_path, record, structurally_validated=True)

    def _append(
        self,
        path: Path,
        record: dict[str, object],
        *,
        structurally_validated: bool = False,
    ) -> None:
        try:
            encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
            if not structurally_validated and any(
                marker in encoded.lower() for marker in FORBIDDEN_DIAGNOSTIC
            ):
                return
            with self._lock:
                self.root.mkdir(parents=True, exist_ok=True)
                if path.exists() and path.stat().st_size >= DIAGNOSTIC_LIMIT_BYTES:
                    for generation in range(DIAGNOSTIC_GENERATIONS - 1, 0, -1):
                        source = path.with_suffix(f".jsonl.{generation}")
                        target = path.with_suffix(f".jsonl.{generation + 1}")
                        if source.exists():
                            source.replace(target)
                    path.replace(path.with_suffix(".jsonl.1"))
                with path.open("a", encoding="utf-8") as output:
                    output.write(encoded + "\n")
        except (OSError, TypeError, ValueError):
            return


class StartupDiagnostics:
    """Launch-correlated browser milestones written off the rendering thread."""

    ALLOWED = {"home_script_started", "home_first_paint", "home_interactive"}

    def __init__(self, app_support_dir: Path, env: Mapping[str, str]) -> None:
        launch_id = env.get("HEY_JARVIS_LAUNCH_ID", "")
        profile = env.get("HEY_JARVIS_BUILD_PROFILE", "")
        sample_kind = env.get("HEY_JARVIS_STARTUP_SAMPLE_KIND", "unspecified")
        self.launch_id = launch_id if SAFE_DIAGNOSTIC.fullmatch(launch_id) else None
        self.profile = profile if profile in {"debug", "release"} else None
        self.sample_kind = sample_kind if sample_kind in {"cold", "warm", "unspecified"} else "unspecified"
        self.path = app_support_dir / "diagnostics" / "startup-python.jsonl"
        self._lock = threading.Lock()

    def record_webview(self, stage: str, elapsed_ms: int) -> None:
        if (
            self.launch_id is None
            or self.profile is None
            or stage not in self.ALLOWED
            or isinstance(elapsed_ms, bool)
            or not isinstance(elapsed_ms, int)
            or not 0 <= elapsed_ms <= 300_000
        ):
            return
        record = {
            "schema": "hey-jarvis-startup-v1",
            "launch_id": self.launch_id,
            "build_profile": self.profile,
            "sample_kind": self.sample_kind,
            "component": "webview",
            "stage": stage,
            "receipt_elapsed_ms": None,
            "process_elapsed_ms": elapsed_ms,
        }
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size >= 256 * 1024:
                    for generation in range(4, 0, -1):
                        source = self.path.with_suffix(f".jsonl.{generation}")
                        target = self.path.with_suffix(f".jsonl.{generation + 1}")
                        if source.exists():
                            source.replace(target)
                    self.path.replace(self.path.with_suffix(".jsonl.1"))
                with self.path.open("a", encoding="utf-8") as output:
                    output.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        except OSError:
            return


def run_packaging_smoke() -> int:
    """Prove the frozen default TFLite and deterministic fake paths offline."""

    from src.main import run_fake_backend_smoke
    from src.wake_word import missing_wake_word_model_paths

    started = time.monotonic()
    missing = missing_wake_word_model_paths(
        model_name="hey_jarvis",
        inference_framework="tflite",
    )
    if missing:
        print(json.dumps({"ok": False, "reason": "wake_assets_missing"}, sort_keys=True))
        return 1
    settings = load_settings(env={}, env_file=None)
    detector = _build_wake_detector(settings, logger=LOGGER)
    detector.preload()
    if run_fake_backend_smoke() != 0:
        print(json.dumps({"ok": False, "reason": "fake_backend_failed"}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "architecture": __import__("platform").machine(),
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "inference": "tflite",
                "model": "hey_jarvis",
                "ok": True,
            },
            sort_keys=True,
        )
    )
    return 0


def validate_openai_credential(
    api_key: str,
    *,
    urlopen: Callable[..., object] = urllib.request.urlopen,
) -> None:
    request = urllib.request.Request(
        OPENAI_MODELS_URL,
        method="GET",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urlopen(request, timeout=10):
            return
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise ProductRuntimeError("openai_credential_invalid") from exc
        raise ProductRuntimeError("openai_service_unavailable") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProductRuntimeError("offline") from exc


def parse_private_credentials(line: str) -> dict[str, str]:
    if (
        not line
        or len(line.encode("utf-8")) > PRIVATE_BOOTSTRAP_MAX_BYTES
        or "\x00" in line
    ):
        raise ProductRuntimeError("credential_bootstrap_invalid")
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProductRuntimeError("credential_bootstrap_invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "kind",
        "openai_api_key",
        "finnhub_api_key",
    }:
        raise ProductRuntimeError("credential_bootstrap_invalid")
    openai = payload.get("openai_api_key")
    finnhub = payload.get("finnhub_api_key")
    if (
        payload.get("kind") != "private_credentials"
        or not isinstance(openai, str)
        or not openai.startswith("sk-")
        or not 3 < len(openai) <= 512
        or any(character.isspace() or ord(character) < 32 for character in openai)
        or (finnhub is not None and not isinstance(finnhub, str))
        or (isinstance(finnhub, str) and (not finnhub or len(finnhub) > 512))
        or (
            isinstance(finnhub, str)
            and any(character.isspace() or ord(character) < 32 for character in finnhub)
        )
    ):
        raise ProductRuntimeError("credential_bootstrap_invalid")
    values = {"OPENAI_API_KEY": openai}
    if finnhub is not None:
        values["FINNHUB_API_KEY"] = finnhub
    return values


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
        self._close_lock = threading.Lock()
        self._closed = False

    @classmethod
    def start(
        cls,
        *,
        session_id: str,
        resource_dir: Path,
        app_support_dir: Path,
        env: Mapping[str, str] | None = None,
        startup_event: Callable[[str], None] | None = None,
    ) -> "ProductRuntime":
        emit_startup = startup_event or (lambda _stage: None)
        startup_diagnostics = StartupDiagnostics(app_support_dir, os.environ if env is None else env)
        diagnostics = LifecycleDiagnostics(app_support_dir, session_id)
        diagnostics.record("runtime_starting", "non_listening")
        # Native preferences exclusively own these values for the packaged app.
        # CLI-only tuning/diagnostic environment variables must not reject or
        # redirect an app-side runtime before the native record is applied.
        values = app_runtime_configuration_env(os.environ if env is None else env)
        settings = load_settings(
            env=values,
            env_file=None,
            require_openai_api_key=True,
            backend="realtime",
        )
        emit_startup("settings_loaded")
        validate_openai_credential(settings.openai_api_key)
        emit_startup("credential_validated")
        settings, app_wake_preferences = apply_app_wake_preferences(
            settings,
            app_support_dir / "preferences-v1.json",
        )
        acknowledgement = (resource_dir / ACKNOWLEDGEMENT_RESOURCE).resolve()
        cached_acknowledgement = (resource_dir / CACHED_ACKNOWLEDGEMENT_RESOURCE).resolve()
        cached_acknowledgement_manifest = (
            resource_dir / CACHED_ACKNOWLEDGEMENT_MANIFEST_RESOURCE
        ).resolve()
        cached_farewell = (resource_dir / CACHED_FAREWELL_RESOURCE).resolve()
        cached_farewell_manifest = (resource_dir / CACHED_FAREWELL_MANIFEST_RESOURCE).resolve()
        english_cached_acknowledgement = (
            resource_dir / ENGLISH_CACHED_ACKNOWLEDGEMENT_RESOURCE
        ).resolve()
        english_cached_acknowledgement_manifest = (
            resource_dir / ENGLISH_CACHED_ACKNOWLEDGEMENT_MANIFEST_RESOURCE
        ).resolve()
        english_cached_farewell = (resource_dir / ENGLISH_CACHED_FAREWELL_RESOURCE).resolve()
        english_cached_farewell_manifest = (
            resource_dir / ENGLISH_CACHED_FAREWELL_MANIFEST_RESOURCE
        ).resolve()
        session_expiry_warning_en = (resource_dir / SESSION_EXPIRY_WARNING_EN_RESOURCE).resolve()
        session_expiry_warning_zh = (resource_dir / SESSION_EXPIRY_WARNING_ZH_RESOURCE).resolve()
        ready_chime = (resource_dir / READY_CHIME_RESOURCE).resolve()
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
        emit_startup("wake_model_ready")
        wake_options = build_app_realtime_wake_options(
            settings,
            app_wake_preferences,
            app_support_dir,
        )
        server = build_server(
            "127.0.0.1",
            0,
            real_microphone=True,
            wake_after_arm=True,
            acknowledgement_mode=settings.realtime_acknowledgement_mode,
            farewell_mode=settings.realtime_farewell_mode,
            end_phrases=settings.realtime_end_phrases,
            tool_provider_config=provider_config_from_settings(settings),
            settings=settings,
            capability_lease=session_id,
            cached_acknowledgement_audio_path=cached_acknowledgement,
            cached_acknowledgement_manifest_path=cached_acknowledgement_manifest,
            cached_farewell_audio_path=cached_farewell,
            cached_farewell_manifest_path=cached_farewell_manifest,
            english_cached_acknowledgement_audio_path=english_cached_acknowledgement,
            english_cached_acknowledgement_manifest_path=english_cached_acknowledgement_manifest,
            english_cached_farewell_audio_path=english_cached_farewell,
            english_cached_farewell_manifest_path=english_cached_farewell_manifest,
            session_expiry_warning_en_path=session_expiry_warning_en,
            session_expiry_warning_zh_path=session_expiry_warning_zh,
            app_language_path=app_support_dir / "preferences-v1.json",
            startup_event=startup_diagnostics.record_webview,
            negotiation_failure_sink=diagnostics.record_negotiation_failure,
        )
        server_thread = threading.Thread(
            target=server.serve_forever,
            name="hey-jarvis-loopback",
            daemon=True,
        )
        server_thread.start()
        emit_startup("server_bound")

        player = MacOSPlayer(logger=LOGGER)
        acknowledgement_duration_ms = (
            player.duration_ms(settings.wake_acknowledgement_audio_path)
            if settings.realtime_acknowledgement_mode == "local"
            else None
        )

        def play_acknowledgement() -> None:
            if settings.realtime_acknowledgement_mode == "local":
                player.play_acknowledgement(settings.wake_acknowledgement_audio_path)

        def play_ready_tone() -> None:
            player.play(ready_chime)

        stop_event = threading.Event()
        controller = RealtimeSessionController(
            coordinator=server.coordinator,
            wake_detector=detector,
            play_acknowledgement=play_acknowledgement,
            play_ready_tone=play_ready_tone,
            acknowledgement_duration_ms=acknowledgement_duration_ms,
            idle_timeout_seconds=settings.realtime_idle_timeout_seconds,
            max_duration_seconds=settings.realtime_max_duration_seconds,
            session_expiry_warning_enabled=True,
            wake_recovery_sample_rate=settings.sample_rate,
            wake_recovery_cooldown_seconds=settings.post_playback_wake_cooldown_seconds,
            wake_recovery_quiet_seconds=settings.post_playback_quiet_seconds,
            wake_recovery_quiet_rms=settings.post_playback_quiet_rms,
            wake_recovery_max_seconds=settings.post_playback_max_suppression_seconds,
            **wake_options,
            shutdown_requested=stop_event.is_set,
        )

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
        )
        controller_thread.start()
        emit_startup("controller_started")
        diagnostics.record("runtime_ready", "ready")
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

    def availability(self) -> str:
        return self.server.coordinator.availability()

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self.stop_event.set()
            self.server.coordinator.begin_shutdown()
            self.controller_thread.join(CONTROLLER_SHUTDOWN_TIMEOUT_SECONDS)
            if self.controller_thread.is_alive():
                raise ProductRuntimeError("controller_shutdown_timed_out")
            self.server.shutdown()
            self.server.server_close()
            self.server.coordinator.close()
            close = getattr(self.detector, "close", None)
            if close is not None:
                close()
            self._closed = True


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
    diagnostics: LifecycleDiagnostics | None = None

    def startup_elapsed_ms() -> int:
        return min(300_000, max(0, round((time.monotonic() - PROCESS_STARTED) * 1000)))

    try:
        bootstrap_line = input_stream.readline()
        if not bootstrap_line:
            return 2
        try:
            credentials = parse_private_credentials(bootstrap_line.rstrip("\n"))
        except ProductRuntimeError:
            return 2
        runtime_env = dict(os.environ if env is None else env)
        runtime_env.pop("OPENAI_API_KEY", None)
        runtime_env.pop("FINNHUB_API_KEY", None)
        runtime_env.update(credentials)

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
                diagnostics = LifecycleDiagnostics(
                    Path(payload["app_support_dir"]), session_id
                )
                diagnostics.record("protocol_startup", "non_listening")
                def emit_startup(stage: str) -> None:
                    nonlocal outbound_sequence
                    _write(
                        output_stream,
                        session_id,
                        outbound_sequence,
                        {
                            "kind": "startup_timing",
                            "stage": stage,
                            "elapsed_ms": startup_elapsed_ms(),
                        },
                    )
                    outbound_sequence += 1

                emit_startup("process_started")
                emit_startup("imports_ready")
                emit_startup("runtime_starting")
                try:
                    runtime = runtime_factory(
                        session_id=session_id,
                        resource_dir=Path(payload["resource_dir"]),
                        app_support_dir=Path(payload["app_support_dir"]),
                        env=runtime_env,
                        startup_event=emit_startup,
                    )
                except Exception as exc:
                    diagnostics.record("startup_failed", "non_listening")
                    LOGGER.error("product runtime startup failed: %s", type(exc).__name__)
                    error_code = (
                        exc.code
                        if isinstance(exc, ProductRuntimeError)
                        else type(exc).__name__
                    )
                    _write(
                        output_stream,
                        session_id,
                        outbound_sequence,
                        {
                            "kind": "error",
                            "code": f"startup_{error_code}",
                            "recoverable": True,
                        },
                    )
                    return 1
                emit_startup("runtime_ready")
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
                diagnostics.record("ready_sent", "ready")
                continue

            kind = payload["kind"]
            if kind == "lifecycle" and payload["event"] == "health_check":
                if diagnostics is not None:
                    diagnostics.record("health_check", runtime.availability())
                _write(
                    output_stream,
                    session_id,
                    outbound_sequence,
                    {
                        "kind": "lifecycle",
                        "event": "voice_availability",
                        "detail": runtime.availability(),
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
                if diagnostics is not None:
                    diagnostics.record("shutdown_requested", "stopping")
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
        if diagnostics is not None:
            diagnostics.record("process_stopped", "non_listening")

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if sys.argv[1:] == ["--packaging-smoke"]:
        raise SystemExit(run_packaging_smoke())
    raise SystemExit(run())

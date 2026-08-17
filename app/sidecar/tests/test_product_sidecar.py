import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path


SIDECAR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIDECAR_DIR))

from product_sidecar import (  # noqa: E402
    ACKNOWLEDGEMENT_RESOURCE,
    CACHED_ACKNOWLEDGEMENT_MANIFEST_RESOURCE,
    CACHED_ACKNOWLEDGEMENT_RESOURCE,
    CACHED_FAREWELL_MANIFEST_RESOURCE,
    CACHED_FAREWELL_RESOURCE,
    ENGLISH_CACHED_ACKNOWLEDGEMENT_MANIFEST_RESOURCE,
    ENGLISH_CACHED_ACKNOWLEDGEMENT_RESOURCE,
    ENGLISH_CACHED_FAREWELL_MANIFEST_RESOURCE,
    ENGLISH_CACHED_FAREWELL_RESOURCE,
    READY_CHIME_RESOURCE,
    SESSION_EXPIRY_WARNING_EN_RESOURCE,
    SESSION_EXPIRY_WARNING_ZH_RESOURCE,
    LifecycleDiagnostics,
    ProductRuntime,
    ProductRuntimeError,
    StartupDiagnostics,
    apply_app_wake_preferences,
    app_runtime_configuration_env,
    build_app_realtime_wake_options,
    parse_private_credentials,
    run,
    validate_openai_credential,
)
from src.config import load_settings  # noqa: E402
from src.main import build_realtime_wake_options  # noqa: E402


def message(sequence, payload):
    return json.dumps(
        {
            "protocol_version": 2,
            "sequence": sequence,
            "session_id": "session-product-1",
            "payload": payload,
        }
    )


def credentials(openai="sk-test-private", finnhub=None):
    return json.dumps(
        {
            "kind": "private_credentials",
            "openai_api_key": openai,
            "finnhub_api_key": finnhub,
        }
    )


class FakeRuntime:
    control_url = "http://127.0.0.1:54321/?lease=session-product-1"

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    def availability(self):
        return "wake_listening"


class ProductSidecarTests(unittest.TestCase):
    def test_startup_diagnostics_are_launch_correlated_and_allowlisted(self):
        with tempfile.TemporaryDirectory() as directory:
            diagnostics = StartupDiagnostics(
                Path(directory),
                {
                    "HEY_JARVIS_LAUNCH_ID": "launch-123-456",
                    "HEY_JARVIS_BUILD_PROFILE": "release",
                    "HEY_JARVIS_STARTUP_SAMPLE_KIND": "warm",
                },
            )
            diagnostics.record_webview("home_interactive", 321)
            diagnostics.record_webview("transcript", 400)
            record = json.loads(diagnostics.path.read_text(encoding="utf-8"))
            self.assertEqual(record["launch_id"], "launch-123-456")
            self.assertEqual(record["stage"], "home_interactive")
            self.assertEqual(record["process_elapsed_ms"], 321)
            self.assertNotIn("transcript", json.dumps(record))

    def test_native_runtime_ignores_cli_only_wake_environment(self):
        values = app_runtime_configuration_env(
            {
                "OPENAI_API_KEY": "sk-test",
                "WAKE_MODEL": "hey_jarvis",
                "WAKE_THRESHOLD": "0.99",
                "WAKE_CONFIRMATION_FRAMES": "99",
                "WAKE_DIAGNOSTICS_ENABLED": "1",
                "WAKE_DIAGNOSTICS_DIR": "https://not-local.invalid",
            }
        )
        self.assertEqual(values["OPENAI_API_KEY"], "sk-test")
        self.assertEqual(values["WAKE_MODEL"], "hey_jarvis")
        self.assertNotIn("WAKE_THRESHOLD", values)
        self.assertNotIn("WAKE_CONFIRMATION_FRAMES", values)
        self.assertNotIn("WAKE_DIAGNOSTICS_ENABLED", values)
        self.assertNotIn("WAKE_DIAGNOSTICS_DIR", values)

    def test_native_wake_preferences_override_environment_before_runtime_construction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences-v1.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 5,
                        "smart_speaker_mode": False,
                        "app_language": "en",
                        "app_theme": "night",
                        "wake_diagnostics_enabled": True,
                        "wake_threshold": 0.6,
                        "wake_confirmation_frames": 3,
                    }
                ),
                encoding="utf-8",
            )
            settings = load_settings(
                env={"WAKE_THRESHOLD": "0.5", "WAKE_CONFIRMATION_FRAMES": "2"},
                env_file=None,
            )
            effective, preferences = apply_app_wake_preferences(settings, path)
            self.assertEqual(effective.wake_threshold, 0.6)
            self.assertEqual(effective.wake_confirmation_frames, 3)
            self.assertTrue(preferences.diagnostics_enabled)

            app_options = build_app_realtime_wake_options(
                effective, preferences, Path(directory) / "app-support"
            )
            cli_settings = load_settings(
                env={
                    "BACKEND": "realtime",
                    "WAKE_THRESHOLD": "0.60",
                    "WAKE_CONFIRMATION_FRAMES": "3",
                    "WAKE_DIAGNOSTICS_ENABLED": "1",
                    "WAKE_DIAGNOSTICS_DIR": str(Path(directory) / "cli-diagnostics"),
                },
                env_file=None,
            )
            cli_options = build_realtime_wake_options(cli_settings)
            self.assertEqual(app_options["wake_threshold"], cli_options["wake_threshold"])
            self.assertEqual(
                app_options["wake_confirmation_frames"],
                cli_options["wake_confirmation_frames"],
            )
            self.assertEqual(
                app_options["wake_diagnostics"].path.name,
                cli_options["wake_diagnostics"].path.name,
            )

            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ProductRuntimeError, "preferences_corrupt"):
                apply_app_wake_preferences(settings, path)

    def test_runtime_close_joins_controller_before_tearing_down_dependencies(self):
        calls = []

        class Coordinator:
            def begin_shutdown(self):
                calls.append("begin_shutdown")

            def close(self):
                calls.append("coordinator_close")

        class Server:
            coordinator = Coordinator()

            def shutdown(self):
                calls.append("server_shutdown")

            def server_close(self):
                calls.append("server_close")

        class ControllerThread:
            def join(self, timeout):
                self.timeout = timeout
                calls.append("controller_join")

            def is_alive(self):
                return False

        class Detector:
            def close(self):
                calls.append("detector_close")

        runtime = ProductRuntime(
            server=Server(),
            detector=Detector(),
            controller_thread=ControllerThread(),
            stop_event=__import__("threading").Event(),
            control_url="http://127.0.0.1",
        )

        runtime.close()
        runtime.close()

        self.assertTrue(runtime.stop_event.is_set())
        self.assertEqual(
            calls,
            [
                "begin_shutdown",
                "controller_join",
                "server_shutdown",
                "server_close",
                "coordinator_close",
                "detector_close",
            ],
        )

    def test_lifecycle_diagnostics_are_bounded_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            diagnostics = LifecycleDiagnostics(Path(directory), "session-product-1")
            diagnostics.record("runtime_ready", "wake_listening")
            diagnostics.record("transcript_secret", "ready")
            text = diagnostics.path.read_text(encoding="utf-8")
            record = json.loads(text)
            self.assertEqual(record["event"], "runtime_ready")
            self.assertEqual(record["session"], "session-product-1")
            self.assertNotIn("transcript_secret", text)

    def test_openai_credential_validation_distinguishes_valid_invalid_and_offline(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        calls = []

        def succeeds(request, timeout):
            calls.append((request, timeout))
            return Response()

        validate_openai_credential("sk-valid-test", urlopen=succeeds)
        self.assertEqual(calls[0][1], 10)
        self.assertEqual(calls[0][0].get_header("Authorization"), "Bearer sk-valid-test")

        def unauthorized(_request, timeout):
            del timeout
            raise urllib.error.HTTPError("url", 401, "unauthorized", {}, None)

        with self.assertRaisesRegex(ProductRuntimeError, "openai_credential_invalid"):
            validate_openai_credential("sk-invalid-test", urlopen=unauthorized)

        def offline(_request, timeout):
            del timeout
            raise urllib.error.URLError("offline")

        with self.assertRaisesRegex(ProductRuntimeError, "offline"):
            validate_openai_credential("sk-offline-test", urlopen=offline)

    def test_product_protocol_starts_health_checks_and_closes_runtime(self):
        runtime = FakeRuntime()
        calls = []

        def factory(**kwargs):
            calls.append(kwargs)
            return runtime

        incoming = "\n".join(
            [
                credentials(),
                message(
                    1,
                    {
                        "kind": "startup",
                        "app_version": "0.1.0",
                        "app_support_dir": "/tmp/hey-jarvis-support",
                        "resource_dir": "/tmp/hey-jarvis-resources",
                    },
                ),
                message(
                    2,
                    {"kind": "lifecycle", "event": "health_check", "detail": None},
                ),
                message(3, {"kind": "shutdown", "reason": "test"}),
            ]
        )
        output = io.StringIO()

        self.assertEqual(
            run(
                io.StringIO(incoming),
                output,
                runtime_factory=factory,
                env={"OPENAI_API_KEY": "sk-environment-must-not-win"},
            ),
            0,
        )
        payloads = [
            json.loads(line)["payload"] for line in output.getvalue().splitlines()
        ]
        timings = [payload for payload in payloads if payload["kind"] == "startup_timing"]
        self.assertEqual(
            [payload["stage"] for payload in timings],
            ["process_started", "imports_ready", "runtime_starting", "runtime_ready"],
        )
        ready = next(payload for payload in payloads if payload["kind"] == "ready")
        self.assertEqual(ready["control_url"], runtime.control_url)
        lifecycle = [payload for payload in payloads if payload["kind"] == "lifecycle"]
        self.assertEqual(lifecycle[0]["event"], "voice_availability")
        self.assertEqual(lifecycle[0]["detail"], "wake_listening")
        self.assertEqual(lifecycle[1]["event"], "stopping")
        self.assertTrue(runtime.closed)
        self.assertEqual(calls[0]["resource_dir"], Path("/tmp/hey-jarvis-resources"))
        self.assertEqual(calls[0]["app_support_dir"], Path("/tmp/hey-jarvis-support"))
        self.assertEqual(calls[0]["env"]["OPENAI_API_KEY"], "sk-test-private")
        self.assertNotIn("sk-test-private", output.getvalue())

    def test_startup_failure_is_redacted_and_nonzero(self):
        def factory(**_kwargs):
            raise RuntimeError("OPENAI_API_KEY=sk-private")

        incoming = "\n".join(
            [
                credentials(),
                message(
                    1,
                    {
                        "kind": "startup",
                        "app_version": "0.1.0",
                        "app_support_dir": "/tmp/support",
                        "resource_dir": "/tmp/resources",
                    },
                ),
            ]
        )
        output = io.StringIO()

        self.assertEqual(
            run(io.StringIO(incoming), output, runtime_factory=factory),
            1,
        )
        result = output.getvalue()
        self.assertIn("startup_RuntimeError", result)
        self.assertNotIn("sk-private", result)
        self.assertNotIn("OPENAI_API_KEY", result)

    def test_private_credentials_are_required_and_validated_before_protocol(self):
        self.assertEqual(run(io.StringIO(""), io.StringIO()), 2)
        with self.assertRaises(ProductRuntimeError):
            parse_private_credentials(credentials(openai="not-a-key"))
        with self.assertRaises(ProductRuntimeError):
            parse_private_credentials("{}")

        calls = []

        def factory(**kwargs):
            calls.append(kwargs)
            return FakeRuntime()

        incoming = "\n".join(
            [
                credentials(finnhub="stock-token"),
                message(
                    1,
                    {
                        "kind": "startup",
                        "app_version": "0.1.0",
                        "app_support_dir": "/tmp/support",
                        "resource_dir": "/tmp/resources",
                    },
                ),
            ]
        )
        output = io.StringIO()
        self.assertEqual(run(io.StringIO(incoming), output, runtime_factory=factory), 0)
        self.assertEqual(calls[0]["env"]["FINNHUB_API_KEY"], "stock-token")
        self.assertNotIn("stock-token", output.getvalue())

    def test_acknowledgement_resource_is_relative_to_bundle_resources(self):
        self.assertFalse(ACKNOWLEDGEMENT_RESOURCE.is_absolute())
        self.assertEqual(
            ACKNOWLEDGEMENT_RESOURCE.as_posix(),
            "assets/wake_acknowledgement_alloy.mp3",
        )
        self.assertEqual(
            CACHED_ACKNOWLEDGEMENT_RESOURCE.as_posix(),
            "assets/realtime_acknowledgement_alloy_zh.wav",
        )
        self.assertEqual(
            CACHED_ACKNOWLEDGEMENT_MANIFEST_RESOURCE.as_posix(),
            "assets/realtime_acknowledgement_alloy_zh.json",
        )
        self.assertEqual(CACHED_FAREWELL_RESOURCE.as_posix(), "assets/realtime_farewell_alloy_zh.wav")
        self.assertEqual(
            CACHED_FAREWELL_MANIFEST_RESOURCE.as_posix(),
            "assets/realtime_farewell_alloy_zh.json",
        )
        self.assertEqual(
            ENGLISH_CACHED_ACKNOWLEDGEMENT_RESOURCE.as_posix(),
            "assets/realtime_acknowledgement_alloy_en.wav",
        )
        self.assertEqual(
            ENGLISH_CACHED_ACKNOWLEDGEMENT_MANIFEST_RESOURCE.as_posix(),
            "assets/realtime_acknowledgement_alloy_en.json",
        )
        self.assertEqual(
            ENGLISH_CACHED_FAREWELL_RESOURCE.as_posix(),
            "assets/realtime_farewell_alloy_en.wav",
        )
        self.assertEqual(
            ENGLISH_CACHED_FAREWELL_MANIFEST_RESOURCE.as_posix(),
            "assets/realtime_farewell_alloy_en.json",
        )
        self.assertEqual(SESSION_EXPIRY_WARNING_EN_RESOURCE.as_posix(), "assets/session_expiry_warning_alloy_en.wav")
        self.assertEqual(SESSION_EXPIRY_WARNING_ZH_RESOURCE.as_posix(), "assets/session_expiry_warning_alloy_zh.wav")
        self.assertEqual(READY_CHIME_RESOURCE.as_posix(), "assets/realtime_ready_chime.wav")

    def test_product_runtime_passes_both_languages_to_the_loopback_host(self):
        source = (SIDECAR_DIR / "product_sidecar.py").read_text(encoding="utf-8")
        start = source[source.index("server = build_server("):source.index("server_thread =", source.index("server = build_server("))]
        self.assertIn("cached_acknowledgement_audio_path=cached_acknowledgement", start)
        self.assertIn("cached_farewell_audio_path=cached_farewell", start)
        self.assertIn(
            "english_cached_acknowledgement_audio_path=english_cached_acknowledgement",
            start,
        )
        self.assertIn("english_cached_farewell_audio_path=english_cached_farewell", start)
        self.assertIn("session_expiry_warning_en_path=session_expiry_warning_en", start)
        self.assertIn("session_expiry_warning_zh_path=session_expiry_warning_zh", start)
        self.assertIn('app_language_path=app_support_dir / "preferences-v1.json"', start)

    def test_product_runtime_enables_only_persisted_wake_diagnostics(self):
        source = (SIDECAR_DIR / "product_sidecar.py").read_text(encoding="utf-8")
        self.assertIn("load_app_wake_preferences", source)
        self.assertIn("wake_threshold=app_preferences.threshold", source)
        self.assertIn(
            "wake_confirmation_frames=app_preferences.confirmation_frames",
            source,
        )
        self.assertIn("if app_wake_preferences.diagnostics_enabled", source)
        self.assertIn("WakeDiagnostics(app_support_dir)", source)
        self.assertIn('"wake_threshold": settings.wake_threshold', source)
        self.assertIn('"wake_diagnostics": (', source)
        self.assertIn("**wake_options", source)
        self.assertIn('"WAKE_DIAGNOSTICS_DIR"', source)
        self.assertIn("app_runtime_configuration_env", source)


if __name__ == "__main__":
    unittest.main()

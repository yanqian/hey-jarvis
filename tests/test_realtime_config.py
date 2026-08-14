from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src.config import ConfigError, collect_diagnostics, load_settings
from src.main import build_parser, build_realtime_wake_options, main


class RealtimeConfigTests(unittest.TestCase):
    def test_pipeline_is_default_and_ignores_invalid_inactive_realtime_values(self):
        defaults = load_settings(env={}, env_file=None)
        self.assertEqual(defaults.backend, "pipeline")
        self.assertEqual(defaults.realtime_voice, "alloy")
        self.assertEqual(defaults.realtime_output_volume, 0.5)
        self.assertEqual(defaults.realtime_idle_timeout_seconds, 60.0)
        self.assertEqual(defaults.realtime_server_vad_threshold, 0.8)
        self.assertEqual(defaults.realtime_input_noise_reduction, "far_field")
        self.assertEqual(defaults.realtime_acknowledgement_mode, "cached")
        self.assertEqual(defaults.realtime_farewell_mode, "cached")
        settings = load_settings(
            env={
                "BACKEND": "pipeline",
                "REALTIME_IDLE_TIMEOUT_SECONDS": "not-a-number",
                "REALTIME_BRIDGE_HOST": "0.0.0.0",
            },
            env_file=None,
        )
        self.assertEqual(settings.backend, "pipeline")
        self.assertEqual(settings.realtime_bridge_host, "127.0.0.1")

    def test_realtime_defaults_and_typed_overrides(self):
        settings = load_settings(
            env={
                "BACKEND": "realtime",
                "REALTIME_MODEL": "model-test",
                "REALTIME_VOICE": "voice-test",
                "REALTIME_OUTPUT_VOLUME": "0.65",
                "REALTIME_IDLE_TIMEOUT_SECONDS": "12",
                "REALTIME_MAX_DURATION_SECONDS": "120",
                "REALTIME_SERVER_VAD_ENABLED": "0",
                "REALTIME_SERVER_VAD_THRESHOLD": "0.75",
                "REALTIME_INPUT_NOISE_REDUCTION": "near_field",
                "REALTIME_INPUT_TRANSCRIPTION_ENABLED": "1",
                "REALTIME_ACKNOWLEDGEMENT_MODE": "local",
                "REALTIME_FAREWELL_MODE": "realtime",
                "REALTIME_DEBUG": "1",
                "REALTIME_END_PHRASES": "结束,goodbye",
                "REALTIME_BRIDGE_PORT": "9876",
            },
            env_file=None,
        )
        self.assertEqual(settings.backend, "realtime")
        self.assertEqual(settings.realtime_model, "model-test")
        self.assertEqual(settings.realtime_voice, "voice-test")
        self.assertEqual(settings.realtime_output_volume, 0.65)
        self.assertEqual(settings.realtime_idle_timeout_seconds, 12.0)
        self.assertEqual(settings.realtime_max_duration_seconds, 120.0)
        self.assertFalse(settings.realtime_server_vad_enabled)
        self.assertEqual(settings.realtime_server_vad_threshold, 0.75)
        self.assertEqual(settings.realtime_input_noise_reduction, "near_field")
        self.assertTrue(settings.realtime_input_transcription_enabled)
        self.assertEqual(settings.realtime_acknowledgement_mode, "local")
        self.assertEqual(settings.realtime_farewell_mode, "realtime")
        self.assertEqual(
            load_settings(
                env={"BACKEND": "realtime", "REALTIME_ACKNOWLEDGEMENT_MODE": "realtime"},
                env_file=None,
            ).realtime_acknowledgement_mode,
            "realtime",
        )
        self.assertTrue(settings.realtime_debug)
        self.assertEqual(settings.realtime_end_phrases, ("结束", "goodbye"))
        self.assertEqual(settings.realtime_bridge_port, 9876)

    def test_realtime_wake_tuning_and_diagnostics_are_bounded_and_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / ".env"
            output = root / "wake-evidence"
            env_file.write_text(
                "\n".join(
                    (
                        "BACKEND=realtime",
                        "WAKE_THRESHOLD=0.60",
                        "WAKE_CONFIRMATION_FRAMES=3",
                        "WAKE_DIAGNOSTICS_ENABLED=1",
                        f"WAKE_DIAGNOSTICS_DIR={output}",
                    )
                ),
                encoding="utf-8",
            )

            settings = load_settings(env={}, env_file=env_file)
            options = build_realtime_wake_options(settings)

            self.assertEqual(options["wake_threshold"], 0.6)
            self.assertEqual(options["wake_confirmation_frames"], 3)
            writer = options["wake_diagnostics"]
            self.assertIsNotNone(writer)
            self.assertEqual(writer.path, output / "wake.jsonl")
            self.assertFalse(output.exists())

    def test_realtime_wake_diagnostics_default_off_and_invalid_values_fail_closed(self):
        settings = load_settings(env={"BACKEND": "realtime"}, env_file=None)
        self.assertIsNone(build_realtime_wake_options(settings)["wake_diagnostics"])

        invalid_cases = (
            (
                {"BACKEND": "realtime", "WAKE_THRESHOLD": "0.55"},
                "WAKE_THRESHOLD must be one of 0.50 or 0.60",
            ),
            (
                {"BACKEND": "realtime", "WAKE_CONFIRMATION_FRAMES": "4"},
                "WAKE_CONFIRMATION_FRAMES must be one of 2 or 3",
            ),
            (
                {"BACKEND": "realtime", "WAKE_DIAGNOSTICS_ENABLED": "1"},
                "WAKE_DIAGNOSTICS_DIR is required",
            ),
            (
                {
                    "BACKEND": "realtime",
                    "WAKE_DIAGNOSTICS_ENABLED": "1",
                    "WAKE_DIAGNOSTICS_DIR": "https://example.invalid/logs",
                },
                "must be a local filesystem directory",
            ),
        )
        for env, expected in invalid_cases:
            with self.subTest(env=env):
                with self.assertRaisesRegex(ConfigError, expected):
                    load_settings(env=env, env_file=None)

        pipeline = load_settings(
            env={
                "BACKEND": "pipeline",
                "WAKE_THRESHOLD": "0.55",
                "WAKE_CONFIRMATION_FRAMES": "4",
                "WAKE_DIAGNOSTICS_ENABLED": "not-a-boolean",
                "WAKE_DIAGNOSTICS_DIR": "https://inactive.invalid/logs",
            },
            env_file=None,
        )
        self.assertEqual(pipeline.wake_threshold, 0.55)
        self.assertEqual(pipeline.wake_confirmation_frames, 4)
        self.assertFalse(pipeline.wake_diagnostics_enabled)
        self.assertIsNone(pipeline.wake_diagnostics_dir)

    def test_selected_realtime_rejects_unsafe_or_inconsistent_values(self):
        with self.assertRaises(ConfigError) as caught:
            load_settings(
                env={
                    "BACKEND": "realtime",
                    "REALTIME_IDLE_TIMEOUT_SECONDS": "30",
                    "REALTIME_MAX_DURATION_SECONDS": "20",
                    "REALTIME_BRIDGE_HOST": "0.0.0.0",
                    "REALTIME_ACKNOWLEDGEMENT_MODE": "remote",
                    "REALTIME_FAREWELL_MODE": "local",
                    "REALTIME_OUTPUT_VOLUME": "1.1",
                    "REALTIME_SERVER_VAD_THRESHOLD": "1.1",
                    "REALTIME_INPUT_NOISE_REDUCTION": "studio",
                },
                env_file=None,
            )
        message = str(caught.exception)
        self.assertIn("MAX_DURATION", message)
        self.assertIn("loopback", message)
        self.assertIn("ACKNOWLEDGEMENT_MODE", message)
        self.assertIn("FAREWELL_MODE", message)
        self.assertIn("REALTIME_OUTPUT_VOLUME", message)
        self.assertIn("REALTIME_SERVER_VAD_THRESHOLD", message)
        self.assertIn("REALTIME_INPUT_NOISE_REDUCTION", message)

    def test_cli_override_dispatches_to_realtime_runtime(self):
        args = build_parser().parse_args(["--backend", "realtime", "--dry-run"])
        self.assertEqual(args.backend, "realtime")
        settings = replace(load_settings(env={}, env_file=None), backend="realtime", openai_api_key="configured")
        with patch("src.main.load_settings", return_value=settings), patch(
            "src.main.run_realtime_forever", return_value=0
        ) as realtime:
            self.assertEqual(main(["--backend", "realtime"]), 0)
        realtime.assert_called_once_with(settings)

    def test_diagnostics_separate_pipeline_and_realtime_readiness_without_secrets(self):
        pipeline = collect_diagnostics(
            env={"BACKEND": "pipeline", "REALTIME_BRIDGE_HOST": "bad", "OPENAI_API_KEY": "sk-private"},
            env_file=None,
            python_version=(3, 12),
            afplay_path="/usr/bin/afplay",
            dependency_modules={},
            wake_word_model_paths={},
        )
        pipeline_checks = {check.name: check for check in pipeline.checks}
        self.assertEqual(pipeline_checks["backend:pipeline"].status, "ok")
        self.assertEqual(pipeline_checks["backend:realtime"].status, "skip")

        realtime = collect_diagnostics(
            env={"BACKEND": "realtime", "OPENAI_API_KEY": "sk-private"},
            env_file=None,
            python_version=(3, 12),
            afplay_path="/usr/bin/afplay",
            dependency_modules={},
            wake_word_model_paths={},
        )
        checks = {check.name: check for check in realtime.checks}
        self.assertIn("voice=alloy", checks["realtime:model-voice"].message)
        self.assertIn("output_volume=0.5", checks["realtime:model-voice"].message)
        for name in (
            "realtime:host-assets",
            "realtime:model-voice",
            "realtime:credential",
            "realtime:loopback",
            "realtime:audio-handoff",
        ):
            self.assertEqual(checks[name].status, "ok")
        self.assertIn("server_vad_threshold=0.8", checks["realtime:model-voice"].message)
        self.assertIn("input_noise_reduction=far_field", checks["realtime:model-voice"].message)
        self.assertIn("threshold=0.50", checks["realtime:wake-tuning"].message)
        self.assertIn("confirmation_frames=2", checks["realtime:wake-tuning"].message)
        self.assertIn("disabled", checks["realtime:wake-diagnostics"].message)
        self.assertNotIn("sk-private", "\n".join(check.message for check in realtime.checks))


if __name__ == "__main__":
    unittest.main()

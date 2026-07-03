import tempfile
import unittest
from pathlib import Path

from src.config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_RECORD_SECONDS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SILENCE_SECONDS,
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DEFAULT_WAKE_DEBUG,
    DEFAULT_WAKE_PHRASE,
    DEFAULT_WAKE_THRESHOLD,
    ConfigError,
    collect_diagnostics,
    load_settings,
)


class ConfigTests(unittest.TestCase):
    def test_defaults_do_not_require_openai_key(self):
        settings = load_settings(env={}, env_file=None)

        self.assertIsNone(settings.openai_api_key)
        self.assertEqual(settings.wake_phrase, DEFAULT_WAKE_PHRASE)
        self.assertEqual(settings.wake_threshold, DEFAULT_WAKE_THRESHOLD)
        self.assertEqual(settings.silence_seconds, DEFAULT_SILENCE_SECONDS)
        self.assertEqual(settings.max_record_seconds, DEFAULT_MAX_RECORD_SECONDS)
        self.assertEqual(settings.sample_rate, DEFAULT_SAMPLE_RATE)
        self.assertEqual(settings.transcribe_model, DEFAULT_TRANSCRIBE_MODEL)
        self.assertEqual(settings.chat_model, DEFAULT_CHAT_MODEL)
        self.assertEqual(settings.tts_model, DEFAULT_TTS_MODEL)
        self.assertEqual(settings.tts_voice, DEFAULT_TTS_VOICE)
        self.assertEqual(settings.wake_debug, DEFAULT_WAKE_DEBUG)

    def test_environment_overrides_are_typed(self):
        settings = load_settings(
            env={
                "OPENAI_API_KEY": "sk-test",
                "WAKE_PHRASE": "hello jarvis",
                "WAKE_THRESHOLD": "0.65",
                "SILENCE_SECONDS": "2.25",
                "MAX_RECORD_SECONDS": "30",
                "SAMPLE_RATE": "24000",
                "TRANSCRIBE_MODEL": "transcribe-test",
                "CHAT_MODEL": "chat-test",
                "TTS_MODEL": "tts-test",
                "TTS_VOICE": "verse",
                "WAKE_DEBUG": "1",
            },
            env_file=None,
        )

        self.assertEqual(settings.openai_api_key, "sk-test")
        self.assertEqual(settings.wake_phrase, "hello jarvis")
        self.assertEqual(settings.wake_threshold, 0.65)
        self.assertEqual(settings.silence_seconds, 2.25)
        self.assertEqual(settings.max_record_seconds, 30.0)
        self.assertEqual(settings.sample_rate, 24000)
        self.assertEqual(settings.transcribe_model, "transcribe-test")
        self.assertEqual(settings.chat_model, "chat-test")
        self.assertEqual(settings.tts_model, "tts-test")
        self.assertEqual(settings.tts_voice, "verse")
        self.assertTrue(settings.wake_debug)

    def test_env_file_values_are_loaded_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "OPENAI_API_KEY=from-file",
                        "WAKE_THRESHOLD=0.4",
                        "CHAT_MODEL='file-chat'",
                    ]
                ),
                encoding="utf-8",
            )

            settings = load_settings(env={"CHAT_MODEL": "env-chat"}, env_file=env_path)

        self.assertEqual(settings.openai_api_key, "from-file")
        self.assertEqual(settings.wake_threshold, 0.4)
        self.assertEqual(settings.chat_model, "env-chat")

    def test_invalid_values_are_reported_together(self):
        with self.assertRaises(ConfigError) as caught:
            load_settings(
                env={
                    "WAKE_THRESHOLD": "2",
                    "SILENCE_SECONDS": "10",
                    "MAX_RECORD_SECONDS": "5",
                    "SAMPLE_RATE": "not-an-int",
                    "CHAT_MODEL": "",
                    "WAKE_DEBUG": "maybe",
                },
                env_file=None,
            )

        message = str(caught.exception)
        self.assertIn("WAKE_THRESHOLD must be at most 1.0", message)
        self.assertIn("SAMPLE_RATE must be an integer", message)
        self.assertIn("CHAT_MODEL must not be empty", message)
        self.assertIn("WAKE_DEBUG must be a boolean value", message)
        self.assertIn("MAX_RECORD_SECONDS must be greater than SILENCE_SECONDS", message)

    def test_required_openai_key_has_actionable_error(self):
        with self.assertRaises(ConfigError) as caught:
            load_settings(env={}, env_file=None, require_openai_api_key=True)

        self.assertIn("OPENAI_API_KEY is required", str(caught.exception))

    def test_diagnostics_report_missing_key_without_import_time_crash(self):
        report = collect_diagnostics(
            env={},
            env_file=None,
            python_version=(3, 12),
            afplay_path="/usr/bin/afplay",
            dependency_modules={"json": "json"},
        )

        messages = {check.name: check.message for check in report.checks}
        statuses = {check.name: check.status for check in report.checks}
        self.assertEqual(statuses["python"], "ok")
        self.assertEqual(statuses["afplay"], "ok")
        self.assertEqual(statuses["dependency:json"], "ok")
        self.assertEqual(statuses["OPENAI_API_KEY"], "error")
        self.assertIn("add it to .env or export it", messages["OPENAI_API_KEY"])
        self.assertIn("Grant macOS microphone permission", messages["microphone_permission"])

    def test_diagnostics_report_missing_wake_word_model_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "hey_jarvis_v0.1.onnx"
            report = collect_diagnostics(
                env={"OPENAI_API_KEY": "sk-test"},
                env_file=None,
                python_version=(3, 12),
                afplay_path="/usr/bin/afplay",
                dependency_modules={"json": "json"},
                wake_word_model_paths={"hey_jarvis": missing_path},
            )

        messages = {check.name: check.message for check in report.checks}
        statuses = {check.name: check.status for check in report.checks}
        self.assertEqual(statuses["wake_word_models"], "error")
        self.assertIn("prepare-wake-word", messages["wake_word_models"])

    def test_diagnostics_accept_present_wake_word_model_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_path = Path(tmp_dir) / "hey_jarvis_v0.1.onnx"
            model_path.write_bytes(b"onnx")
            report = collect_diagnostics(
                env={"OPENAI_API_KEY": "sk-test"},
                env_file=None,
                python_version=(3, 12),
                afplay_path="/usr/bin/afplay",
                dependency_modules={"json": "json"},
                wake_word_model_paths={"hey_jarvis": model_path},
            )

        statuses = {check.name: check.status for check in report.checks}
        self.assertEqual(statuses["wake_word_models"], "ok")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import (
    DEFAULT_ARMED_CLIP_REJECT_PEAK,
    DEFAULT_ARMED_MIN_RMS,
    DEFAULT_ARMED_NO_SPEECH_TIMEOUT_SECONDS,
    DEFAULT_ARMED_PRE_ROLL_SECONDS,
    DEFAULT_ARMED_SNR_MULTIPLIER,
    DEFAULT_ARMED_VOICE_REQUIRED_RATIO,
    DEFAULT_ARMED_VOICE_WINDOW_SECONDS,
    DEFAULT_ARMED_VOICE_RMS,
    DEFAULT_CHAT_MODEL,
    DEFAULT_CANCEL_PHRASES,
    DEFAULT_ENABLE_TOOLS,
    DEFAULT_BASE_CURRENCY,
    DEFAULT_MAX_RECORD_SECONDS,
    DEFAULT_FX_PROVIDER,
    DEFAULT_LOCATION,
    DEFAULT_MIN_TRANSCRIPT_LENGTH,
    DEFAULT_MIN_VALID_SPEECH_SECONDS,
    DEFAULT_POST_PLAYBACK_MAX_SUPPRESSION_SECONDS,
    DEFAULT_POST_PLAYBACK_QUIET_RMS,
    DEFAULT_POST_PLAYBACK_QUIET_SECONDS,
    DEFAULT_POST_PLAYBACK_WAKE_COOLDOWN_SECONDS,
    DEFAULT_RECORDING_SILENCE_RMS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SILENCE_SECONDS,
    DEFAULT_STOCK_PROVIDER,
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS,
    DEFAULT_TOOL_ANSWER_NATURALIZATION,
    DEFAULT_TOOL_ROUTER_DEBUG,
    DEFAULT_TTS_INSTRUCTIONS,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_SPEED,
    DEFAULT_TTS_VOICE,
    DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH,
    DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS,
    DEFAULT_WAKE_ACKNOWLEDGEMENT_ENABLED,
    DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT,
    DEFAULT_WAKE_DEBUG,
    DEFAULT_WAKE_BACKEND,
    DEFAULT_WAKE_INFERENCE_FRAMEWORK,
    DEFAULT_WAKE_MODEL,
    DEFAULT_WAKE_PHRASE,
    DEFAULT_WAKE_THRESHOLD,
    DEFAULT_WAKE_CONFIRMATION_FRAMES,
    DEFAULT_WEATHER_PROVIDER,
    ConfigError,
    collect_diagnostics,
    load_settings,
)


class ConfigTests(unittest.TestCase):
    def test_defaults_do_not_require_openai_key(self):
        settings = load_settings(env={}, env_file=None)

        self.assertIsNone(settings.openai_api_key)
        self.assertEqual(settings.wake_backend, "openwakeword")
        self.assertEqual(settings.wake_model, "hey_jarvis")
        self.assertEqual(settings.wake_inference_framework, "tflite")
        self.assertEqual(settings.wake_backend, DEFAULT_WAKE_BACKEND)
        self.assertEqual(settings.wake_model, DEFAULT_WAKE_MODEL)
        self.assertEqual(settings.wake_inference_framework, DEFAULT_WAKE_INFERENCE_FRAMEWORK)
        self.assertEqual(DEFAULT_WAKE_PHRASE, "hey jarvis")
        self.assertEqual(settings.wake_phrase, DEFAULT_WAKE_PHRASE)
        self.assertEqual(settings.wake_threshold, DEFAULT_WAKE_THRESHOLD)
        self.assertEqual(settings.silence_seconds, DEFAULT_SILENCE_SECONDS)
        self.assertEqual(settings.max_record_seconds, DEFAULT_MAX_RECORD_SECONDS)
        self.assertEqual(settings.recording_silence_rms, DEFAULT_RECORDING_SILENCE_RMS)
        self.assertEqual(settings.sample_rate, DEFAULT_SAMPLE_RATE)
        self.assertEqual(settings.transcribe_model, DEFAULT_TRANSCRIBE_MODEL)
        self.assertEqual(settings.chat_model, DEFAULT_CHAT_MODEL)
        self.assertEqual(settings.tts_model, DEFAULT_TTS_MODEL)
        self.assertEqual(settings.tts_voice, DEFAULT_TTS_VOICE)
        self.assertIsNone(DEFAULT_TTS_INSTRUCTIONS)
        self.assertIsNone(settings.tts_instructions)
        self.assertEqual(settings.tts_speed, DEFAULT_TTS_SPEED)
        self.assertEqual(settings.enable_tools, DEFAULT_ENABLE_TOOLS)
        self.assertEqual(settings.tool_router_debug, DEFAULT_TOOL_ROUTER_DEBUG)
        self.assertEqual(settings.tool_answer_naturalization, DEFAULT_TOOL_ANSWER_NATURALIZATION)
        self.assertEqual(settings.weather_provider, DEFAULT_WEATHER_PROVIDER)
        self.assertEqual(settings.fx_provider, DEFAULT_FX_PROVIDER)
        self.assertEqual(settings.stock_provider, DEFAULT_STOCK_PROVIDER)
        self.assertEqual(settings.tool_http_timeout_seconds, DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS)
        self.assertEqual(settings.default_location, DEFAULT_LOCATION)
        self.assertEqual(settings.default_base_currency, DEFAULT_BASE_CURRENCY)
        self.assertIsNone(settings.finnhub_api_key)
        self.assertEqual(settings.wake_acknowledgement_enabled, DEFAULT_WAKE_ACKNOWLEDGEMENT_ENABLED)
        self.assertEqual(settings.wake_acknowledgement_text, DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT)
        self.assertEqual(settings.wake_acknowledgement_audio_path, DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH)
        self.assertEqual(settings.wake_acknowledgement_drain_seconds, DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS)
        self.assertTrue(settings.ack_guard_enabled)
        self.assertEqual(settings.ack_guard_seconds, 0.60)
        self.assertEqual(settings.ack_guard_min_quiet_seconds, 0.16)
        self.assertEqual(settings.ack_guard_quiet_rms, 600.0)
        self.assertEqual(settings.ack_guard_max_buffer_seconds, 1.0)
        self.assertEqual(settings.wake_debug, DEFAULT_WAKE_DEBUG)
        self.assertEqual(settings.post_playback_wake_cooldown_seconds, DEFAULT_POST_PLAYBACK_WAKE_COOLDOWN_SECONDS)
        self.assertEqual(settings.post_playback_quiet_seconds, DEFAULT_POST_PLAYBACK_QUIET_SECONDS)
        self.assertEqual(settings.post_playback_quiet_rms, DEFAULT_POST_PLAYBACK_QUIET_RMS)
        self.assertEqual(settings.post_playback_max_suppression_seconds, DEFAULT_POST_PLAYBACK_MAX_SUPPRESSION_SECONDS)
        self.assertEqual(settings.wake_confirmation_frames, DEFAULT_WAKE_CONFIRMATION_FRAMES)
        self.assertEqual(settings.armed_no_speech_timeout_seconds, DEFAULT_ARMED_NO_SPEECH_TIMEOUT_SECONDS)
        self.assertEqual(settings.armed_voice_rms, DEFAULT_ARMED_VOICE_RMS)
        self.assertEqual(settings.armed_min_rms, DEFAULT_ARMED_MIN_RMS)
        self.assertEqual(settings.armed_snr_multiplier, DEFAULT_ARMED_SNR_MULTIPLIER)
        self.assertEqual(settings.armed_voice_window_seconds, DEFAULT_ARMED_VOICE_WINDOW_SECONDS)
        self.assertEqual(settings.armed_voice_required_ratio, DEFAULT_ARMED_VOICE_REQUIRED_RATIO)
        self.assertEqual(settings.armed_clip_reject_peak, DEFAULT_ARMED_CLIP_REJECT_PEAK)
        self.assertEqual(settings.armed_pre_roll_seconds, DEFAULT_ARMED_PRE_ROLL_SECONDS)
        self.assertEqual(settings.armed_baseline_seconds, 0.30)
        self.assertEqual(settings.armed_baseline_min_chunks, 3)
        self.assertTrue(settings.armed_require_baseline)
        self.assertTrue(settings.armed_last_chunk_must_be_voiced)
        self.assertEqual(settings.min_valid_speech_seconds, DEFAULT_MIN_VALID_SPEECH_SECONDS)
        self.assertEqual(settings.min_transcript_length, DEFAULT_MIN_TRANSCRIPT_LENGTH)
        self.assertEqual(settings.cancel_phrases, DEFAULT_CANCEL_PHRASES)

    def test_environment_overrides_are_typed(self):
        settings = load_settings(
            env={
                "OPENAI_API_KEY": "sk-test",
                "WAKE_BACKEND": "openwakeword",
                "WAKE_MODEL": "timer",
                "WAKE_INFERENCE_FRAMEWORK": "tflite",
                "WAKE_PHRASE": "computer",
                "WAKE_THRESHOLD": "0.65",
                "SILENCE_SECONDS": "2.25",
                "MAX_RECORD_SECONDS": "30",
                "RECORDING_SILENCE_RMS": "850",
                "SAMPLE_RATE": "24000",
                "TRANSCRIBE_MODEL": "transcribe-test",
                "CHAT_MODEL": "chat-test",
                "TTS_MODEL": "tts-test",
                "TTS_VOICE": "verse",
                "TTS_INSTRUCTIONS": "Speak with warm, quick, upbeat energy.",
                "TTS_SPEED": "1.2",
                "ENABLE_TOOLS": "0",
                "TOOL_ROUTER_DEBUG": "1",
                "TOOL_ANSWER_NATURALIZATION": "0",
                "WEATHER_PROVIDER": "open-meteo",
                "FX_PROVIDER": "frankfurter",
                "STOCK_PROVIDER": "finnhub",
                "TOOL_HTTP_TIMEOUT_SECONDS": "2.75",
                "DEFAULT_LOCATION": "Singapore",
                "DEFAULT_BASE_CURRENCY": "sgd",
                "FINNHUB_API_KEY": "fh-test",
                "WAKE_ACKNOWLEDGEMENT_ENABLED": "0",
                "WAKE_ACKNOWLEDGEMENT_TEXT": "yes?",
                "WAKE_ACKNOWLEDGEMENT_AUDIO_PATH": "tmp/custom-ack.mp3",
                "WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS": "0.8",
                "ACK_GUARD_ENABLED": "0",
                "ACK_GUARD_SECONDS": "0.7",
                "ACK_GUARD_MIN_QUIET_SECONDS": "0.2",
                "ACK_GUARD_QUIET_RMS": "700",
                "ACK_GUARD_MAX_BUFFER_SECONDS": "1.2",
                "WAKE_DEBUG": "1",
                "POST_PLAYBACK_WAKE_COOLDOWN_SECONDS": "2.5",
                "POST_PLAYBACK_QUIET_SECONDS": "0.75",
                "POST_PLAYBACK_QUIET_RMS": "650",
                "POST_PLAYBACK_MAX_SUPPRESSION_SECONDS": "5",
                "WAKE_CONFIRMATION_FRAMES": "3",
                "ARMED_NO_SPEECH_TIMEOUT_SECONDS": "1.25",
                "ARMED_VOICE_RMS": "900",
                "ARMED_MIN_RMS": "950",
                "ARMED_SNR_MULTIPLIER": "3.0",
                "ARMED_VOICE_WINDOW_SECONDS": "0.4",
                "ARMED_VOICE_REQUIRED_RATIO": "0.8",
                "ARMED_CLIP_REJECT_PEAK": "31000",
                "ARMED_PRE_ROLL_SECONDS": "0.6",
                "ARMED_BASELINE_SECONDS": "0.5",
                "ARMED_BASELINE_MIN_CHUNKS": "4",
                "ARMED_REQUIRE_BASELINE": "0",
                "ARMED_LAST_CHUNK_MUST_BE_VOICED": "0",
                "MIN_VALID_SPEECH_SECONDS": "0.4",
                "MIN_TRANSCRIPT_LENGTH": "3",
                "CANCEL_PHRASES": "stop,no thanks,算了",
            },
            env_file=None,
        )

        self.assertEqual(settings.openai_api_key, "sk-test")
        self.assertEqual(settings.wake_backend, "openwakeword")
        self.assertEqual(settings.wake_model, "timer")
        self.assertEqual(settings.wake_inference_framework, "tflite")
        self.assertEqual(settings.wake_phrase, "computer")
        self.assertEqual(settings.wake_threshold, 0.65)
        self.assertEqual(settings.silence_seconds, 2.25)
        self.assertEqual(settings.max_record_seconds, 30.0)
        self.assertEqual(settings.recording_silence_rms, 850.0)
        self.assertEqual(settings.sample_rate, 24000)
        self.assertEqual(settings.transcribe_model, "transcribe-test")
        self.assertEqual(settings.chat_model, "chat-test")
        self.assertEqual(settings.tts_model, "tts-test")
        self.assertEqual(settings.tts_voice, "verse")
        self.assertEqual(settings.tts_instructions, "Speak with warm, quick, upbeat energy.")
        self.assertEqual(settings.tts_speed, 1.2)
        self.assertFalse(settings.enable_tools)
        self.assertTrue(settings.tool_router_debug)
        self.assertFalse(settings.tool_answer_naturalization)
        self.assertEqual(settings.weather_provider, "open-meteo")
        self.assertEqual(settings.fx_provider, "frankfurter")
        self.assertEqual(settings.stock_provider, "finnhub")
        self.assertEqual(settings.tool_http_timeout_seconds, 2.75)
        self.assertEqual(settings.default_location, "Singapore")
        self.assertEqual(settings.default_base_currency, "SGD")
        self.assertEqual(settings.finnhub_api_key, "fh-test")
        self.assertFalse(settings.wake_acknowledgement_enabled)
        self.assertEqual(settings.wake_acknowledgement_text, "yes?")
        self.assertEqual(settings.wake_acknowledgement_audio_path, Path("tmp/custom-ack.mp3"))
        self.assertEqual(settings.wake_acknowledgement_drain_seconds, 0.8)
        self.assertFalse(settings.ack_guard_enabled)
        self.assertEqual(settings.ack_guard_seconds, 0.7)
        self.assertEqual(settings.ack_guard_min_quiet_seconds, 0.2)
        self.assertEqual(settings.ack_guard_quiet_rms, 700.0)
        self.assertEqual(settings.ack_guard_max_buffer_seconds, 1.2)
        self.assertTrue(settings.wake_debug)
        self.assertEqual(settings.post_playback_wake_cooldown_seconds, 2.5)
        self.assertEqual(settings.post_playback_quiet_seconds, 0.75)
        self.assertEqual(settings.post_playback_quiet_rms, 650.0)
        self.assertEqual(settings.post_playback_max_suppression_seconds, 5.0)
        self.assertEqual(settings.wake_confirmation_frames, 3)
        self.assertEqual(settings.armed_no_speech_timeout_seconds, 1.25)
        self.assertEqual(settings.armed_voice_rms, 900.0)
        self.assertEqual(settings.armed_min_rms, 950.0)
        self.assertEqual(settings.armed_snr_multiplier, 3.0)
        self.assertEqual(settings.armed_voice_window_seconds, 0.4)
        self.assertEqual(settings.armed_voice_required_ratio, 0.8)
        self.assertEqual(settings.armed_clip_reject_peak, 31000)
        self.assertEqual(settings.armed_pre_roll_seconds, 0.6)
        self.assertEqual(settings.armed_baseline_seconds, 0.5)
        self.assertEqual(settings.armed_baseline_min_chunks, 4)
        self.assertFalse(settings.armed_require_baseline)
        self.assertFalse(settings.armed_last_chunk_must_be_voiced)
        self.assertEqual(settings.min_valid_speech_seconds, 0.4)
        self.assertEqual(settings.min_transcript_length, 3)
        self.assertEqual(settings.cancel_phrases, ("stop", "no thanks", "算了"))

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
                    "WAKE_BACKEND": "unsupported",
                    "WAKE_INFERENCE_FRAMEWORK": "bad-framework",
                    "SILENCE_SECONDS": "10",
                    "MAX_RECORD_SECONDS": "5",
                    "RECORDING_SILENCE_RMS": "-1",
                    "SAMPLE_RATE": "not-an-int",
                    "CHAT_MODEL": "",
                    "TTS_SPEED": "fast",
                    "ENABLE_TOOLS": "maybe",
                    "TOOL_ROUTER_DEBUG": "maybe",
                    "TOOL_ANSWER_NATURALIZATION": "maybe",
                    "WEATHER_PROVIDER": "",
                    "FX_PROVIDER": "",
                    "STOCK_PROVIDER": "",
                    "TOOL_HTTP_TIMEOUT_SECONDS": "0",
                    "DEFAULT_LOCATION": "",
                    "DEFAULT_BASE_CURRENCY": "",
                    "WAKE_ACKNOWLEDGEMENT_ENABLED": "maybe",
                    "WAKE_ACKNOWLEDGEMENT_TEXT": "",
                    "WAKE_ACKNOWLEDGEMENT_AUDIO_PATH": "",
                    "WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS": "-1",
                    "WAKE_DEBUG": "maybe",
                    "POST_PLAYBACK_WAKE_COOLDOWN_SECONDS": "2",
                    "POST_PLAYBACK_QUIET_SECONDS": "-0.1",
                    "POST_PLAYBACK_QUIET_RMS": "-1",
                    "POST_PLAYBACK_MAX_SUPPRESSION_SECONDS": "0.5",
                    "WAKE_CONFIRMATION_FRAMES": "0",
                    "ARMED_NO_SPEECH_TIMEOUT_SECONDS": "-1",
                    "ARMED_VOICE_RMS": "-1",
                    "ARMED_MIN_RMS": "-1",
                    "ARMED_SNR_MULTIPLIER": "-1",
                    "ARMED_VOICE_WINDOW_SECONDS": "-1",
                    "ARMED_VOICE_REQUIRED_RATIO": "1.5",
                    "ARMED_CLIP_REJECT_PEAK": "40000",
                    "ARMED_PRE_ROLL_SECONDS": "-1",
                    "MIN_VALID_SPEECH_SECONDS": "-0.1",
                    "MIN_TRANSCRIPT_LENGTH": "0",
                },
                env_file=None,
            )

        message = str(caught.exception)
        self.assertIn("WAKE_THRESHOLD must be at most 1.0", message)
        self.assertIn("WAKE_BACKEND must be one of openwakeword", message)
        self.assertIn("WAKE_INFERENCE_FRAMEWORK must be one of tflite, onnx", message)
        self.assertIn("SAMPLE_RATE must be an integer", message)
        self.assertIn("RECORDING_SILENCE_RMS must be at least 0.0", message)
        self.assertIn("CHAT_MODEL must not be empty", message)
        self.assertIn("TTS_SPEED must be a number", message)
        self.assertIn("ENABLE_TOOLS must be a boolean value", message)
        self.assertIn("TOOL_ROUTER_DEBUG must be a boolean value", message)
        self.assertIn("TOOL_ANSWER_NATURALIZATION must be a boolean value", message)
        self.assertIn("WEATHER_PROVIDER must not be empty", message)
        self.assertIn("FX_PROVIDER must not be empty", message)
        self.assertIn("STOCK_PROVIDER must not be empty", message)
        self.assertIn("TOOL_HTTP_TIMEOUT_SECONDS must be at least 0.1", message)
        self.assertIn("DEFAULT_LOCATION must not be empty", message)
        self.assertIn("DEFAULT_BASE_CURRENCY must not be empty", message)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_ENABLED must be a boolean value", message)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_TEXT must not be empty", message)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_AUDIO_PATH must not be empty", message)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS must be at least 0.0", message)
        self.assertIn("WAKE_DEBUG must be a boolean value", message)
        self.assertIn("POST_PLAYBACK_QUIET_SECONDS must be at least 0.0", message)
        self.assertIn("POST_PLAYBACK_QUIET_RMS must be at least 0.0", message)
        self.assertIn("POST_PLAYBACK_MAX_SUPPRESSION_SECONDS must be greater than or equal", message)
        self.assertIn("WAKE_CONFIRMATION_FRAMES must be at least 1", message)
        self.assertIn("ARMED_NO_SPEECH_TIMEOUT_SECONDS must be at least 0.0", message)
        self.assertIn("ARMED_VOICE_RMS must be at least 0.0", message)
        self.assertIn("ARMED_MIN_RMS must be at least 0.0", message)
        self.assertIn("ARMED_SNR_MULTIPLIER must be at least 0.0", message)
        self.assertIn("ARMED_VOICE_WINDOW_SECONDS must be at least 0.0", message)
        self.assertIn("ARMED_VOICE_REQUIRED_RATIO must be at most 1.0", message)
        self.assertIn("ARMED_CLIP_REJECT_PEAK must be at most 32768", message)
        self.assertIn("ARMED_PRE_ROLL_SECONDS must be at least 0.0", message)
        self.assertIn("MIN_VALID_SPEECH_SECONDS must be at least 0.0", message)
        self.assertIn("MIN_TRANSCRIPT_LENGTH must be at least 1", message)
        self.assertIn("MAX_RECORD_SECONDS must be greater than SILENCE_SECONDS", message)

    def test_tts_speed_range_is_validated(self):
        for invalid_speed, expected_message in (
            ("0.24", "TTS_SPEED must be at least 0.25"),
            ("4.1", "TTS_SPEED must be at most 4.0"),
        ):
            with self.subTest(invalid_speed=invalid_speed):
                with self.assertRaises(ConfigError) as caught:
                    load_settings(env={"TTS_SPEED": invalid_speed}, env_file=None)

                self.assertIn(expected_message, str(caught.exception))

    def test_blank_tts_instructions_are_ignored(self):
        settings = load_settings(env={"TTS_INSTRUCTIONS": "   "}, env_file=None)

        self.assertIsNone(settings.tts_instructions)

    def test_required_openai_key_has_actionable_error(self):
        with self.assertRaises(ConfigError) as caught:
            load_settings(env={}, env_file=None, require_openai_api_key=True)

        self.assertIn("OPENAI_API_KEY is required", str(caught.exception))

    def test_macos_arm64_onnx_selection_fails_fast(self):
        with patch("src.wake_word.platform.system", return_value="Darwin"):
            with patch("src.wake_word.platform.machine", return_value="arm64"):
                with self.assertRaises(ConfigError) as caught:
                    load_settings(env={"WAKE_INFERENCE_FRAMEWORK": "onnx"}, env_file=None)

        self.assertIn("WAKE_INFERENCE_FRAMEWORK=onnx is disabled on macOS ARM64", str(caught.exception))

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

    def test_diagnostics_report_tool_provider_configuration_without_secret_values(self):
        report = collect_diagnostics(
            env={
                "OPENAI_API_KEY": "sk-test",
                "FINNHUB_API_KEY": "fh-secret",
                "DEFAULT_LOCATION": "Singapore",
                "DEFAULT_BASE_CURRENCY": "sgd",
            },
            env_file=None,
            python_version=(3, 12),
            afplay_path="/usr/bin/afplay",
            dependency_modules={"json": "json"},
            wake_word_model_paths={},
        )

        messages = {check.name: check.message for check in report.checks}
        statuses = {check.name: check.status for check in report.checks}
        self.assertEqual(statuses["tool_providers"], "ok")
        self.assertIn("weather=open-meteo", messages["tool_providers"])
        self.assertIn("fx=frankfurter", messages["tool_providers"])
        self.assertIn("stock=finnhub", messages["tool_providers"])
        self.assertIn("default_base_currency=SGD", messages["tool_providers"])
        self.assertEqual(statuses["FINNHUB_API_KEY"], "ok")
        self.assertNotIn("fh-secret", "\n".join(messages.values()))

    def test_diagnostics_report_missing_stock_provider_credentials(self):
        report = collect_diagnostics(
            env={"OPENAI_API_KEY": "sk-test", "STOCK_PROVIDER": "finnhub"},
            env_file=None,
            python_version=(3, 12),
            afplay_path="/usr/bin/afplay",
            dependency_modules={"json": "json"},
            wake_word_model_paths={},
        )

        messages = {check.name: check.message for check in report.checks}
        statuses = {check.name: check.status for check in report.checks}
        self.assertEqual(statuses["FINNHUB_API_KEY"], "warning")
        self.assertIn("stock quote requests", messages["FINNHUB_API_KEY"])

    def test_diagnostics_report_missing_wake_word_model_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "hey_jarvis_v0.1.tflite"
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

    def test_diagnostics_report_missing_wake_acknowledgement_audio(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ack_path = Path(tmp_dir) / "ack.mp3"
            report = collect_diagnostics(
                env={
                    "OPENAI_API_KEY": "sk-test",
                    "WAKE_ACKNOWLEDGEMENT_AUDIO_PATH": str(ack_path),
                },
                env_file=None,
                python_version=(3, 12),
                afplay_path="/usr/bin/afplay",
                dependency_modules={"json": "json"},
                wake_word_model_paths={},
            )

        messages = {check.name: check.message for check in report.checks}
        statuses = {check.name: check.status for check in report.checks}
        self.assertEqual(statuses["wake_acknowledgement_audio"], "error")
        self.assertIn("--prepare-acknowledgement", messages["wake_acknowledgement_audio"])

    def test_diagnostics_accept_present_wake_acknowledgement_audio(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ack_path = Path(tmp_dir) / "ack.mp3"
            ack_path.write_bytes(b"ack")
            report = collect_diagnostics(
                env={
                    "OPENAI_API_KEY": "sk-test",
                    "WAKE_ACKNOWLEDGEMENT_AUDIO_PATH": str(ack_path),
                },
                env_file=None,
                python_version=(3, 12),
                afplay_path="/usr/bin/afplay",
                dependency_modules={"json": "json"},
                wake_word_model_paths={},
            )

        statuses = {check.name: check.status for check in report.checks}
        self.assertEqual(statuses["wake_acknowledgement_audio"], "ok")

    def test_diagnostics_accept_present_wake_word_model_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_path = Path(tmp_dir) / "hey_jarvis_v0.1.tflite"
            model_path.write_bytes(b"tflite")
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

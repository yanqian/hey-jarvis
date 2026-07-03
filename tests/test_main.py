import logging
import unittest
from unittest.mock import patch

from src.config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_RECORD_SECONDS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SILENCE_SECONDS,
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DEFAULT_WAKE_PHRASE,
    DEFAULT_WAKE_THRESHOLD,
    Settings,
)
from src.main import run_assistant_forever


def make_settings():
    return Settings(
        openai_api_key="sk-test",
        wake_phrase=DEFAULT_WAKE_PHRASE,
        wake_threshold=DEFAULT_WAKE_THRESHOLD,
        silence_seconds=DEFAULT_SILENCE_SECONDS,
        max_record_seconds=DEFAULT_MAX_RECORD_SECONDS,
        sample_rate=DEFAULT_SAMPLE_RATE,
        transcribe_model=DEFAULT_TRANSCRIBE_MODEL,
        chat_model=DEFAULT_CHAT_MODEL,
        tts_model=DEFAULT_TTS_MODEL,
        tts_voice=DEFAULT_TTS_VOICE,
    )


class FakeWakeWordDetector:
    def __init__(self, threshold, logger=None):
        self.threshold = threshold
        self.logger = logger

    def preload(self):
        EVENTS.append("preload")


class FakeMicrophone:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        EVENTS.append("close_microphone")


class FakeStateMachine:
    def __init__(self, **kwargs):
        EVENTS.append("build_machine")
        self.kwargs = kwargs

    def run_once(self):
        EVENTS.append("run_once")
        raise KeyboardInterrupt


EVENTS = []


class MainRuntimeTests(unittest.TestCase):
    def setUp(self):
        EVENTS.clear()

    def test_real_assistant_preloads_wake_word_before_opening_microphone(self):
        logging.getLogger("hey_jarvis")

        def fake_open_microphone_stream(**kwargs):
            EVENTS.append("open_microphone")
            return FakeMicrophone()

        with patch("src.main.load_settings", return_value=make_settings()):
            with patch("src.main.WakeWordDetector", FakeWakeWordDetector):
                with patch("src.main.open_microphone_stream", side_effect=fake_open_microphone_stream):
                    with patch("src.main.VoiceAssistantStateMachine", FakeStateMachine):
                        with patch("src.main.build_openai_client", return_value=object()):
                            with patch("src.main.MacOSPlayer", return_value=object()):
                                with self.assertLogs("hey_jarvis", level="INFO"):
                                    result = run_assistant_forever()

        self.assertEqual(result, 130)
        self.assertLess(EVENTS.index("preload"), EVENTS.index("open_microphone"))
        self.assertEqual(EVENTS, ["preload", "open_microphone", "build_machine", "run_once", "close_microphone"])


if __name__ == "__main__":
    unittest.main()

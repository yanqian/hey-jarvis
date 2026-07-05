import logging
import tempfile
import unittest
import wave
from pathlib import Path

from src.config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_RECORD_SECONDS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SILENCE_SECONDS,
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DEFAULT_WAKE_BACKEND,
    DEFAULT_WAKE_INFERENCE_FRAMEWORK,
    DEFAULT_WAKE_MODEL,
    DEFAULT_WAKE_PHRASE,
    DEFAULT_WAKE_THRESHOLD,
    Settings,
)
from src.openai_client import OpenAIClientError
from src.recorder import RecordingResult
from src.state_machine import AssistantState, VoiceAssistantStateMachine


def make_settings(*, wake_debug=False):
    return Settings(
        openai_api_key="sk-test",
        wake_backend=DEFAULT_WAKE_BACKEND,
        wake_model=DEFAULT_WAKE_MODEL,
        wake_inference_framework=DEFAULT_WAKE_INFERENCE_FRAMEWORK,
        wake_phrase=DEFAULT_WAKE_PHRASE,
        wake_threshold=DEFAULT_WAKE_THRESHOLD,
        silence_seconds=DEFAULT_SILENCE_SECONDS,
        max_record_seconds=DEFAULT_MAX_RECORD_SECONDS,
        sample_rate=DEFAULT_SAMPLE_RATE,
        transcribe_model=DEFAULT_TRANSCRIBE_MODEL,
        chat_model=DEFAULT_CHAT_MODEL,
        tts_model=DEFAULT_TTS_MODEL,
        tts_voice=DEFAULT_TTS_VOICE,
        wake_debug=wake_debug,
    )


class FakeAudioSource:
    def __init__(self):
        self.chunks = [b"\x00\x00", b"\x01\x00"]

    def read_chunk(self):
        return self.chunks.pop(0)


class FakeWakeDetector:
    def __init__(self):
        self.detected_chunks = []

    def detect(self, pcm_chunk):
        self.detected_chunks.append(pcm_chunk)
        return pcm_chunk == b"\x01\x00"

    def score(self, pcm_chunk):
        self.detected_chunks.append(pcm_chunk)
        return 1.0 if pcm_chunk == b"\x01\x00" else 0.0


class FakeOpenAIClient:
    def __init__(self, *, fail_at=None):
        self.transcribed_path = None
        self.tts_output_path = None
        self.fail_at = fail_at
        self.chat_calls = 0
        self.tts_calls = 0

    def transcribe_audio(self, path):
        self.transcribed_path = Path(path)
        if self.fail_at == "transcribe":
            raise OpenAIClientError("OpenAI transcription returned empty text")
        return "what is two plus two?"

    def ask_chatgpt(self, text, history):
        self.chat_calls += 1
        if self.fail_at == "chat":
            raise OpenAIClientError("OpenAI chat response returned empty text")
        history.append({"role": "user", "content": text})
        answer = "Two plus two is four."
        history.append({"role": "assistant", "content": answer})
        return answer

    def text_to_speech(self, text, output_path):
        self.tts_calls += 1
        if self.fail_at == "tts":
            raise OpenAIClientError("OpenAI text-to-speech request failed: timeout")
        self.tts_output_path = Path(output_path)
        self.tts_output_path.write_bytes(text.encode("utf-8"))


class FakePlayer:
    def __init__(self):
        self.played = []

    def play(self, path):
        played_path = Path(path)
        if not played_path.is_file():
            raise RuntimeError("output file missing")
        self.played.append(played_path)


def fake_record_audio(source, *, sample_rate, output_path, **kwargs):
    path = Path(output_path)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * 160)
    return RecordingResult(path=path, duration_seconds=0.01, chunks_recorded=1, stopped_by="test")


class StateMachineTests(unittest.TestCase):
    def test_run_once_completes_full_loop_and_returns_to_wait_wake(self):
        logger = logging.getLogger("tests.state_machine")
        audio_source = FakeAudioSource()
        wake_detector = FakeWakeDetector()
        openai_client = FakeOpenAIClient()
        player = FakePlayer()
        history = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.wav"
            output_path = Path(tmp_dir) / "output.mp3"
            machine = VoiceAssistantStateMachine(
                settings=make_settings(),
                audio_source=audio_source,
                wake_detector=wake_detector,
                openai_client=openai_client,
                player=player,
                history=history,
                record_audio=fake_record_audio,
                input_path=input_path,
                output_path=output_path,
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(result.transcription, "what is two plus two?")
        self.assertEqual(result.answer, "Two plus two is four.")
        self.assertEqual(openai_client.transcribed_path, input_path)
        self.assertEqual(openai_client.tts_output_path, output_path)
        self.assertEqual(openai_client.chat_calls, 1)
        self.assertEqual(openai_client.tts_calls, 1)
        self.assertEqual(player.played, [output_path])
        self.assertEqual(history[-1], {"role": "assistant", "content": "Two plus two is four."})
        log_output = "\n".join(logs.output)
        self.assertIn("State WAIT_WAKE: wake word detected", log_output)
        self.assertIn("Transition WAIT_WAKE -> RECORDING", log_output)
        self.assertIn("Transition PLAYING -> WAIT_WAKE", log_output)

    def test_wake_debug_logs_scores_during_wait_wake(self):
        logger = logging.getLogger("tests.state_machine.debug")
        audio_source = FakeAudioSource()
        wake_detector = FakeWakeDetector()

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(wake_debug=True),
                audio_source=audio_source,
                wake_detector=wake_detector,
                openai_client=FakeOpenAIClient(),
                player=FakePlayer(),
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                machine.run_once()

        log_output = "\n".join(logs.output)
        self.assertIn("Wake debug:", log_output)
        self.assertIn("rms=", log_output)
        self.assertIn("peak=", log_output)
        self.assertIn("overflow=false", log_output)
        self.assertIn("score=1.000000000", log_output)
        self.assertIn("threshold=0.500000000", log_output)

    def test_empty_transcription_returns_to_wait_wake_without_crashing(self):
        logger = logging.getLogger("tests.state_machine.empty_transcription")
        audio_source = FakeAudioSource()
        openai_client = FakeOpenAIClient(fail_at="transcribe")
        player = FakePlayer()

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.wav"
            output_path = Path(tmp_dir) / "output.mp3"
            machine = VoiceAssistantStateMachine(
                settings=make_settings(),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fake_record_audio,
                input_path=input_path,
                output_path=output_path,
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(result.transcription, "")
        self.assertEqual(result.answer, "")
        self.assertEqual(result.error, "OpenAI transcription returned empty text")
        self.assertEqual(openai_client.transcribed_path, input_path)
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [])
        log_output = "\n".join(logs.output)
        self.assertIn("Recoverable OpenAI error in state TRANSCRIBE", log_output)
        self.assertIn("Transition TRANSCRIBE -> WAIT_WAKE", log_output)
        self.assertIn("State WAIT_WAKE: ready for the next wake word", log_output)

    def test_chat_error_returns_to_wait_wake_without_tts_or_playback(self):
        logger = logging.getLogger("tests.state_machine.chat_error")
        openai_client = FakeOpenAIClient(fail_at="chat")
        player = FakePlayer()

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(),
                audio_source=FakeAudioSource(),
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO"):
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(result.transcription, "what is two plus two?")
        self.assertEqual(result.answer, "")
        self.assertEqual(result.error, "OpenAI chat response returned empty text")
        self.assertEqual(openai_client.chat_calls, 1)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [])

    def test_tts_error_returns_to_wait_wake_without_playback(self):
        logger = logging.getLogger("tests.state_machine.tts_error")
        openai_client = FakeOpenAIClient(fail_at="tts")
        player = FakePlayer()

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(),
                audio_source=FakeAudioSource(),
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO"):
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(result.transcription, "what is two plus two?")
        self.assertEqual(result.answer, "Two plus two is four.")
        self.assertEqual(result.error, "OpenAI text-to-speech request failed: timeout")
        self.assertEqual(openai_client.tts_calls, 1)
        self.assertEqual(player.played, [])

    def test_unexpected_transcription_error_is_not_swallowed(self):
        class BrokenOpenAIClient(FakeOpenAIClient):
            def transcribe_audio(self, path):
                raise RuntimeError("programming mistake")

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(),
                audio_source=FakeAudioSource(),
                wake_detector=FakeWakeDetector(),
                openai_client=BrokenOpenAIClient(),
                player=FakePlayer(),
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
            )

            with self.assertRaises(RuntimeError) as caught:
                machine.run_once()

        self.assertIn("programming mistake", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

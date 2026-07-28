import logging
import struct
import tempfile
import unittest
import wave
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src.config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_RECORD_SECONDS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SILENCE_SECONDS,
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH,
    DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS,
    DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT,
    DEFAULT_WAKE_BACKEND,
    DEFAULT_WAKE_INFERENCE_FRAMEWORK,
    DEFAULT_WAKE_MODEL,
    DEFAULT_WAKE_PHRASE,
    DEFAULT_WAKE_THRESHOLD,
    Settings,
)
from src.main import (
    build_parser,
    main,
    run_acknowledgement_benchmark,
    run_assistant_forever,
    run_prepare_acknowledgement,
    run_text_debug,
    run_wake_debug,
    run_wake_file_debug,
)


def make_settings(
    *,
    wake_acknowledgement_enabled=False,
    wake_acknowledgement_audio_path=DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH,
):
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
        wake_acknowledgement_enabled=wake_acknowledgement_enabled,
        wake_acknowledgement_text=DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT,
        wake_acknowledgement_audio_path=wake_acknowledgement_audio_path,
        wake_acknowledgement_drain_seconds=DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS,
    )


class FakeWakeWordDetector:
    frame_length = 1280
    sample_rate = DEFAULT_SAMPLE_RATE

    def __init__(self, threshold, model_name=None, inference_framework=None, vad_threshold=None, logger=None):
        self.threshold = threshold
        self.model_name = model_name
        self.inference_framework = inference_framework
        self.vad_threshold = vad_threshold
        self.logger = logger

    def preload(self):
        EVENTS.append("preload")


class FakeMicrophone:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        EVENTS.append("close_microphone")


class FakeDebugSource:
    def __init__(self, chunks=None):
        self.chunks = list(
            chunks
            or [
                struct.pack("<hh", 100, -100),
                struct.pack("<hh", 1000, -1000),
            ]
        )
        self.last_overflowed = False

    def read_chunk(self):
        chunk = self.chunks.pop(0)
        self.last_overflowed = not self.last_overflowed
        return chunk


class FakeDebugDetector:
    frame_length = 1280
    sample_rate = DEFAULT_SAMPLE_RATE
    model_name = DEFAULT_WAKE_MODEL
    model_key = DEFAULT_WAKE_MODEL
    inference_framework = DEFAULT_WAKE_INFERENCE_FRAMEWORK

    def __init__(self, scores):
        self.scores = list(scores)
        self.preloaded = False

    def preload(self):
        self.preloaded = True

    def score(self, pcm_chunk):
        return self.scores.pop(0)

    def loaded_model_keys(self):
        return (self.model_key,)


class FakeStateMachine:
    def __init__(self, **kwargs):
        EVENTS.append("build_machine")
        self.kwargs = kwargs

    def run_once(self):
        EVENTS.append("run_once")
        raise KeyboardInterrupt


class FakePreparationClient:
    def __init__(self):
        self.tts_calls = []

    def text_to_speech(self, text, output_path):
        self.tts_calls.append((text, Path(output_path)))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"ack")


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

    def test_parser_exposes_wake_debug_flags(self):
        help_text = build_parser().format_help()

        self.assertIn("--wake-debug", help_text)
        self.assertIn("--wake-file", help_text)
        self.assertIn("--wake-debug-output", help_text)
        self.assertIn("--prepare-acknowledgement", help_text)
        self.assertIn("--benchmark-acknowledgement", help_text)
        self.assertIn("--benchmark-iterations", help_text)
        self.assertIn("--text", help_text)

    def test_acknowledgement_benchmark_output_is_bounded_and_privacy_safe(self):
        class Trial:
            index = 1
            process_start_call_ms = 3
            process_lifetime_ms = 497
            total_wall_ms = 500
            derived_overhead_ms = 20

        class Benchmark:
            asset_duration_ms = 480
            trials = (Trial(),)
            median_process_start_call_ms = 3
            median_process_lifetime_ms = 497
            median_total_wall_ms = 500
            median_derived_overhead_ms = 20

        output = StringIO()
        settings = make_settings(
            wake_acknowledgement_audio_path=Path("/private/voice/secret-ack.mp3")
        )
        with patch("src.main.benchmark_audio_playback", return_value=Benchmark()):
            result = run_acknowledgement_benchmark(
                iterations=1,
                settings=settings,
                player=object(),
                output=output,
            )

        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("asset_duration_ms=480", text)
        self.assertIn("sample=cold_candidate", text)
        self.assertIn("process_start_call_ms=3", text)
        self.assertIn("process_lifetime_ms=497", text)
        self.assertIn("derived_overhead_ms=20", text)
        self.assertIn("acoustic_onset=unmeasured", text)
        self.assertNotIn("secret-ack", text)
        self.assertNotIn("嗯", text)

    def test_main_dispatches_acknowledgement_benchmark(self):
        with patch("src.main.run_acknowledgement_benchmark", return_value=0) as run:
            self.assertEqual(
                main(["--benchmark-acknowledgement", "--benchmark-iterations", "3"]),
                0,
            )
        run.assert_called_once_with(iterations=3)

    def test_prepare_acknowledgement_uses_existing_tts_boundary_once(self):
        client = FakePreparationClient()

        with tempfile.TemporaryDirectory() as tmp_dir:
            ack_path = Path(tmp_dir) / "ack.mp3"
            output = StringIO()
            with redirect_stdout(output):
                result = run_prepare_acknowledgement(
                    settings=make_settings(
                        wake_acknowledgement_enabled=True,
                        wake_acknowledgement_audio_path=ack_path,
                    ),
                    openai_client=client,
                )

            self.assertEqual(result, 0)
            self.assertTrue(ack_path.is_file())

        self.assertEqual(client.tts_calls, [(DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT, ack_path)])
        self.assertIn("Prepared wake acknowledgement audio:", output.getvalue())

    def test_text_debug_prints_router_output_without_runtime_backends(self):
        output = StringIO()

        with redirect_stdout(output):
            result = run_text_debug("2 + 2")

        self.assertEqual(result, 0)
        text = output.getvalue()
        self.assertIn("input=2 + 2", text)
        self.assertIn("route=calculator", text)
        self.assertIn("tool=safe_calculator", text)
        self.assertIn("result_status=success", text)
        self.assertIn("final_answer=The answer is 4.", text)

    def test_real_assistant_reports_missing_acknowledgement_before_microphone(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_ack = Path(tmp_dir) / "missing-ack.mp3"
            settings = make_settings(
                wake_acknowledgement_enabled=True,
                wake_acknowledgement_audio_path=missing_ack,
            )
            with patch("src.main.load_settings", return_value=settings):
                with patch("src.main.open_microphone_stream") as open_microphone:
                    with self.assertLogs("hey_jarvis", level="ERROR") as logs:
                        result = run_assistant_forever()

        self.assertEqual(result, 1)
        open_microphone.assert_not_called()
        self.assertIn("--prepare-acknowledgement", "\n".join(logs.output))

    def test_live_wake_debug_prints_levels_overflow_score_and_threshold(self):
        output = StringIO()
        detector = FakeDebugDetector([0.1, 0.9])

        result = run_wake_debug(
            max_frames=2,
            settings=make_settings(),
            audio_source=FakeDebugSource(),
            wake_detector=detector,
            output=output,
        )

        lines = output.getvalue().splitlines()
        self.assertEqual(result, 0)
        self.assertEqual(len(lines), 4)
        self.assertTrue(detector.preloaded)
        self.assertEqual(lines[0], "wake_debug metadata model=hey_jarvis framework=tflite loaded_models=hey_jarvis")
        self.assertIn("wake_debug frame=1", lines[1])
        self.assertIn("rms=100.0", lines[1])
        self.assertIn("peak=100", lines[1])
        self.assertIn("overflow=true", lines[1])
        self.assertIn("score=0.100000000", lines[1])
        self.assertIn("threshold=0.500000000", lines[1])
        self.assertIn("detected=false", lines[1])
        self.assertIn("score=0.900000000", lines[2])
        self.assertIn("detected=true", lines[2])
        self.assertEqual(
            lines[3],
            "wake_debug summary frames=2 max_score=0.900000000 "
            "max_scores={hey_jarvis:0.900000000} threshold=0.500000000 detected_frames=1",
        )

    def test_live_wake_debug_writes_requested_wav_with_scored_chunks(self):
        output = StringIO()
        first_chunk = struct.pack("<hh", 1, -1)
        second_chunk = struct.pack("<hh", 2, -2)

        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "capture" / "wake-debug.wav"
            result = run_wake_debug(
                max_frames=2,
                debug_output_path=wav_path,
                settings=make_settings(),
                audio_source=FakeDebugSource([first_chunk, second_chunk]),
                wake_detector=FakeDebugDetector([0.000000123, 0.81]),
                output=output,
            )

            with wave.open(str(wav_path), "rb") as wav_file:
                self.assertEqual(wav_file.getnchannels(), 1)
                self.assertEqual(wav_file.getsampwidth(), 2)
                self.assertEqual(wav_file.getframerate(), DEFAULT_SAMPLE_RATE)
                self.assertEqual(wav_file.readframes(4), first_chunk + second_chunk)

        self.assertEqual(result, 0)
        lines = output.getvalue().splitlines()
        self.assertIn("score=0.000000123", lines[1])
        self.assertEqual(
            lines[-1],
            "wake_debug summary frames=2 max_score=0.810000000 "
            "max_scores={hey_jarvis:0.810000000} threshold=0.500000000 detected_frames=1",
        )

    def test_wake_debug_output_requires_live_debug_mode(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                main(["--wake-debug-output", "tmp/wake-debug.wav"])

    def test_wake_file_debug_scores_generated_wav_fixture(self):
        output = StringIO()

        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "wake.wav"
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(DEFAULT_SAMPLE_RATE)
                wav_file.writeframes(struct.pack("<hhhh", 0, 500, -500, 0))

            result = run_wake_file_debug(
                wav_path,
                settings=make_settings(),
                wake_detector=FakeDebugDetector([0.45]),
                output=output,
            )

        lines = output.getvalue().splitlines()
        self.assertEqual(result, 0)
        self.assertEqual(lines[0], "wake_file metadata model=hey_jarvis framework=tflite loaded_models=hey_jarvis")
        self.assertIn("wake_file frame=1", lines[1])
        self.assertIn("rms=353.6", lines[1])
        self.assertIn("peak=500", lines[1])
        self.assertIn("overflow=false", lines[1])
        self.assertIn("score=0.450000000", lines[1])
        self.assertEqual(
            lines[2],
            "wake_file summary frames=1 max_score=0.450000000 "
            "max_scores={hey_jarvis:0.450000000} threshold=0.500000000 detected_frames=0",
        )

    def test_wake_file_debug_scores_short_final_chunk(self):
        output = StringIO()

        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "short-final.wav"
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(DEFAULT_SAMPLE_RATE)
                wav_file.writeframes(b"\x00\x00" * 1280)
                wav_file.writeframes(struct.pack("<h", 777))

            result = run_wake_file_debug(
                wav_path,
                settings=make_settings(),
                wake_detector=FakeDebugDetector([0.0, 0.000001234]),
                output=output,
            )

        lines = output.getvalue().splitlines()
        self.assertEqual(result, 0)
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], "wake_file metadata model=hey_jarvis framework=tflite loaded_models=hey_jarvis")
        self.assertIn("wake_file frame=2", lines[2])
        self.assertIn("peak=777", lines[2])
        self.assertIn("score=0.000001234", lines[2])
        self.assertEqual(
            lines[3],
            "wake_file summary frames=2 max_score=0.000001234 "
            "max_scores={hey_jarvis:0.000001234} threshold=0.500000000 detected_frames=0",
        )


if __name__ == "__main__":
    unittest.main()

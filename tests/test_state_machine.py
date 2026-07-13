import logging
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from src.config import (
    DEFAULT_ACK_GUARD_MAX_BUFFER_SECONDS,
    DEFAULT_ACK_GUARD_MIN_QUIET_SECONDS,
    DEFAULT_ACK_GUARD_QUIET_RMS,
    DEFAULT_ARMED_BASELINE_MIN_CHUNKS,
    DEFAULT_ARMED_BASELINE_SECONDS,
    DEFAULT_ARMED_CLIP_REJECT_PEAK,
    DEFAULT_ARMED_MIN_RMS,
    DEFAULT_ARMED_NO_SPEECH_TIMEOUT_SECONDS,
    DEFAULT_ARMED_PRE_ROLL_SECONDS,
    DEFAULT_ARMED_SNR_MULTIPLIER,
    DEFAULT_ARMED_VOICE_REQUIRED_RATIO,
    DEFAULT_ARMED_VOICE_WINDOW_SECONDS,
    DEFAULT_ARMED_VOICE_RMS,
    DEFAULT_CANCEL_PHRASES,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_RECORD_SECONDS,
    DEFAULT_MIN_TRANSCRIPT_LENGTH,
    DEFAULT_MIN_VALID_SPEECH_SECONDS,
    DEFAULT_POST_PLAYBACK_MAX_SUPPRESSION_SECONDS,
    DEFAULT_POST_PLAYBACK_QUIET_RMS,
    DEFAULT_POST_PLAYBACK_QUIET_SECONDS,
    DEFAULT_POST_PLAYBACK_WAKE_COOLDOWN_SECONDS,
    DEFAULT_RECORDING_SILENCE_RMS,
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
    DEFAULT_WAKE_CONFIRMATION_FRAMES,
    Settings,
)
from src.openai_client import OpenAIClientError
from src.recorder import RecordingResult
from src.state_machine import AssistantState, VoiceAssistantStateMachine, _PostAckBoundaryResult
from src.vad import VadResult
from src.tools import ToolResult, ToolRoute


def make_settings(
    *,
    enable_tools=False,
    wake_debug=False,
    post_playback_wake_cooldown_seconds=DEFAULT_POST_PLAYBACK_WAKE_COOLDOWN_SECONDS,
    post_playback_quiet_seconds=DEFAULT_POST_PLAYBACK_QUIET_SECONDS,
    post_playback_quiet_rms=DEFAULT_POST_PLAYBACK_QUIET_RMS,
    post_playback_max_suppression_seconds=DEFAULT_POST_PLAYBACK_MAX_SUPPRESSION_SECONDS,
    wake_confirmation_frames=DEFAULT_WAKE_CONFIRMATION_FRAMES,
    wake_acknowledgement_enabled=False,
    wake_acknowledgement_text=DEFAULT_WAKE_ACKNOWLEDGEMENT_TEXT,
    wake_acknowledgement_audio_path=DEFAULT_WAKE_ACKNOWLEDGEMENT_AUDIO_PATH,
    wake_acknowledgement_drain_seconds=DEFAULT_WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS,
    ack_guard_enabled=False,
    ack_guard_min_quiet_seconds=DEFAULT_ACK_GUARD_MIN_QUIET_SECONDS,
    ack_guard_quiet_rms=DEFAULT_ACK_GUARD_QUIET_RMS,
    ack_guard_max_buffer_seconds=DEFAULT_ACK_GUARD_MAX_BUFFER_SECONDS,
    armed_no_speech_timeout_seconds=DEFAULT_ARMED_NO_SPEECH_TIMEOUT_SECONDS,
    armed_voice_rms=DEFAULT_ARMED_VOICE_RMS,
    armed_min_rms=DEFAULT_ARMED_MIN_RMS,
    armed_snr_multiplier=DEFAULT_ARMED_SNR_MULTIPLIER,
    armed_voice_window_seconds=DEFAULT_ARMED_VOICE_WINDOW_SECONDS,
    armed_voice_required_ratio=DEFAULT_ARMED_VOICE_REQUIRED_RATIO,
    armed_clip_reject_peak=DEFAULT_ARMED_CLIP_REJECT_PEAK,
    armed_pre_roll_seconds=DEFAULT_ARMED_PRE_ROLL_SECONDS,
    armed_baseline_seconds=DEFAULT_ARMED_BASELINE_SECONDS,
    armed_baseline_min_chunks=DEFAULT_ARMED_BASELINE_MIN_CHUNKS,
    armed_require_baseline=True,
    armed_last_chunk_must_be_voiced=True,
    min_valid_speech_seconds=DEFAULT_MIN_VALID_SPEECH_SECONDS,
    min_transcript_length=DEFAULT_MIN_TRANSCRIPT_LENGTH,
    cancel_phrases=DEFAULT_CANCEL_PHRASES,
    recording_silence_rms=DEFAULT_RECORDING_SILENCE_RMS,
    armed_vad_required_ratio=0.50,
    armed_vad_min_frames=2,
    recording_vad_enabled=False,
    recording_vad_end_ratio=0.25,
    recording_vad_speech_ratio=0.50,
    recording_hangover_seconds=0.30,
    recording_end_silence_seconds=DEFAULT_SILENCE_SECONDS,
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
        recording_silence_rms=recording_silence_rms,
        sample_rate=DEFAULT_SAMPLE_RATE,
        transcribe_model=DEFAULT_TRANSCRIBE_MODEL,
        chat_model=DEFAULT_CHAT_MODEL,
        tts_model=DEFAULT_TTS_MODEL,
        tts_voice=DEFAULT_TTS_VOICE,
        enable_tools=enable_tools,
        wake_acknowledgement_enabled=wake_acknowledgement_enabled,
        wake_acknowledgement_text=wake_acknowledgement_text,
        wake_acknowledgement_audio_path=wake_acknowledgement_audio_path,
        wake_acknowledgement_drain_seconds=wake_acknowledgement_drain_seconds,
        ack_guard_enabled=ack_guard_enabled,
        ack_guard_min_quiet_seconds=ack_guard_min_quiet_seconds,
        ack_guard_quiet_rms=ack_guard_quiet_rms,
        ack_guard_max_buffer_seconds=ack_guard_max_buffer_seconds,
        wake_debug=wake_debug,
        post_playback_wake_cooldown_seconds=post_playback_wake_cooldown_seconds,
        post_playback_quiet_seconds=post_playback_quiet_seconds,
        post_playback_quiet_rms=post_playback_quiet_rms,
        post_playback_max_suppression_seconds=post_playback_max_suppression_seconds,
        wake_confirmation_frames=wake_confirmation_frames,
        armed_no_speech_timeout_seconds=armed_no_speech_timeout_seconds,
        armed_voice_rms=armed_voice_rms,
        armed_min_rms=armed_min_rms,
        armed_snr_multiplier=armed_snr_multiplier,
        armed_voice_window_seconds=armed_voice_window_seconds,
        armed_voice_required_ratio=armed_voice_required_ratio,
        armed_clip_reject_peak=armed_clip_reject_peak,
        armed_pre_roll_seconds=armed_pre_roll_seconds,
        armed_baseline_seconds=armed_baseline_seconds,
        armed_baseline_min_chunks=armed_baseline_min_chunks,
        armed_require_baseline=armed_require_baseline,
        armed_last_chunk_must_be_voiced=armed_last_chunk_must_be_voiced,
        min_valid_speech_seconds=min_valid_speech_seconds,
        min_transcript_length=min_transcript_length,
        cancel_phrases=cancel_phrases,
        armed_vad_required_ratio=armed_vad_required_ratio,
        armed_vad_min_frames=armed_vad_min_frames,
        recording_vad_enabled=recording_vad_enabled,
        recording_vad_end_ratio=recording_vad_end_ratio,
        recording_vad_speech_ratio=recording_vad_speech_ratio,
        recording_hangover_seconds=recording_hangover_seconds,
        recording_end_silence_seconds=recording_end_silence_seconds,
    )


def pcm_chunk(sample, frames=1280):
    return sample.to_bytes(2, byteorder="little", signed=True) * frames


WAKE_CHUNK = pcm_chunk(1)
QUIET_CHUNK = pcm_chunk(0)
LOUD_CHUNK = pcm_chunk(2000)
MODERATE_CHUNK = pcm_chunk(800)
NOISE_CHUNK = pcm_chunk(400)
CLIPPED_CHUNK = pcm_chunk(32767)
USER_CLIPPED_CHUNK = pcm_chunk(-32768)
SPEECH_CHUNKS = [LOUD_CHUNK, LOUD_CHUNK, LOUD_CHUNK, LOUD_CHUNK]


class FakeAudioSource:
    def __init__(self, chunks=None, *, fallback_chunk=QUIET_CHUNK):
        self.chunks = list(chunks if chunks is not None else [QUIET_CHUNK, WAKE_CHUNK, WAKE_CHUNK, *SPEECH_CHUNKS])
        self.fallback_chunk = fallback_chunk
        self.read_chunks = []
        self.last_overflowed = False

    def read_chunk(self):
        chunk = self.chunks.pop(0) if self.chunks else self.fallback_chunk
        self.read_chunks.append(chunk)
        self.last_overflowed = chunk == b"overflow"
        return WAKE_CHUNK if chunk == b"overflow" else chunk


class FakeWakeDetector:
    def __init__(self):
        self.detected_chunks = []

    def detect(self, pcm_chunk):
        self.detected_chunks.append(pcm_chunk)
        return pcm_chunk.startswith(b"\x01\x00")

    def score(self, pcm_chunk):
        self.detected_chunks.append(pcm_chunk)
        return 1.0 if pcm_chunk.startswith(b"\x01\x00") else 0.0


class FakeVadDetector:
    is_enabled = True

    def __init__(self, ratio):
        self.ratio = ratio

    def analyze(self, pcm_chunk, sample_rate):
        total_frames = max(1, len(pcm_chunk) // 640)
        voiced_frames = round(total_frames * self.ratio)
        return VadResult(self.ratio, voiced_frames, total_frames)

    def voiced_ratio(self, pcm_chunk, sample_rate):
        return self.ratio


class FakeOpenAIClient:
    def __init__(self, *, fail_at=None, transcription="what is two plus two?"):
        self.transcribed_path = None
        self.tts_output_path = None
        self.fail_at = fail_at
        self.chat_calls = 0
        self.tts_calls = 0
        self.transcription = transcription

    def transcribe_audio(self, path):
        self.transcribed_path = Path(path)
        if self.fail_at == "transcribe":
            raise OpenAIClientError("OpenAI transcription returned empty text")
        return self.transcription

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


class FakePlaybackHandle:
    def __init__(self, running_polls, *, wait_error=None):
        self.running_polls = running_polls
        self.poll_calls = 0
        self.wait_calls = 0
        self.wait_error = wait_error

    def poll(self):
        self.poll_calls += 1
        if self.poll_calls <= self.running_polls:
            return None
        return 0

    def wait(self):
        self.wait_calls += 1
        if self.wait_error is not None:
            raise self.wait_error


class FakeAsyncPlayer(FakePlayer):
    def __init__(self, running_polls, *, wait_error=None):
        super().__init__()
        self.handle = FakePlaybackHandle(running_polls, wait_error=wait_error)
        self.started = []

    def start(self, path):
        self.started.append(Path(path))
        return self.handle


def fake_record_audio(source, *, sample_rate, output_path, **kwargs):
    path = Path(output_path)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(LOUD_CHUNK * 8)
    return RecordingResult(path=path, duration_seconds=0.64, chunks_recorded=8, stopped_by="test")


def fake_silent_record_audio(source, *, sample_rate, output_path, **kwargs):
    path = Path(output_path)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(QUIET_CHUNK * 8)
    return RecordingResult(path=path, duration_seconds=0.64, chunks_recorded=8, stopped_by="silence")


class StateMachineTests(unittest.TestCase):
    def test_synchronized_ack_handoff_preserves_immediate_question_prefix(self):
        logger = logging.getLogger("tests.state_machine.synchronized_ack_immediate_speech")
        audio_source = FakeAudioSource(
            [
                WAKE_CHUNK,
                WAKE_CHUNK,
                QUIET_CHUNK,
                LOUD_CHUNK,
                LOUD_CHUNK,
                LOUD_CHUNK,
                LOUD_CHUNK,
                LOUD_CHUNK,
                LOUD_CHUNK,
            ],
            fallback_chunk=QUIET_CHUNK,
        )
        player = FakeAsyncPlayer(running_polls=3)
        recorded_prefix = []

        def capture_recording(source, *, sample_rate, output_path, **kwargs):
            for _ in range(4):
                recorded_prefix.append(source.read_chunk())
            return fake_record_audio(source, sample_rate=sample_rate, output_path=output_path, **kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            ack_path = Path(tmp_dir) / "ack.mp3"
            ack_path.write_bytes(b"ack")
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=str(ack_path),
                    ack_guard_enabled=True,
                    armed_baseline_seconds=0.30,
                    armed_baseline_min_chunks=3,
                    armed_voice_window_seconds=0.30,
                    armed_voice_required_ratio=0.75,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(transcription="一加一等于几"),
                player=player,
                record_audio=capture_recording,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertEqual(result.transcription, "一加一等于几")
        self.assertEqual(recorded_prefix, [QUIET_CHUNK, LOUD_CHUNK, LOUD_CHUNK, LOUD_CHUNK])
        log_output = "\n".join(logs.output)
        self.assertIn("synchronized live handoff", log_output)
        self.assertIn("post_ack_synchronized=true", log_output)
        self.assertIn("post_ack_quiet_observed=false", log_output)
        self.assertIn("post_ack_boundary_ready=true", log_output)
        self.assertIn("post_ack_suppressed_chunks=0", log_output)
        self.assertIn("preserved_chunks=2", log_output)
        self.assertIn("noise_seed_count=1", log_output)
        self.assertIn("quarantined_overlap_chunks=1", log_output)
        self.assertIn("result=recording_started", log_output)

    def test_synchronized_ack_tail_without_sustained_speech_cancels_locally(self):
        logger = logging.getLogger("tests.state_machine.synchronized_ack_tail")
        audio_source = FakeAudioSource(
            [WAKE_CHUNK, WAKE_CHUNK, CLIPPED_CHUNK, LOUD_CHUNK],
            fallback_chunk=QUIET_CHUNK,
        )
        player = FakeAsyncPlayer(running_polls=1)
        openai_client = FakeOpenAIClient()

        def fail_record(*args, **kwargs):
            raise AssertionError("one live tail chunk must not trigger recording")

        with tempfile.TemporaryDirectory() as tmp_dir:
            ack_path = Path(tmp_dir) / "ack.mp3"
            ack_path.write_bytes(b"ack")
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=str(ack_path),
                    ack_guard_enabled=True,
                    armed_no_speech_timeout_seconds=0.40,
                    armed_baseline_seconds=0.30,
                    armed_baseline_min_chunks=3,
                    armed_voice_window_seconds=0.30,
                    armed_voice_required_ratio=0.75,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fail_record,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "no_speech_after_wake")
        self.assertIsNone(openai_client.transcribed_path)
        log_output = "\n".join(logs.output)
        self.assertIn("post_ack_synchronized=true", log_output)
        self.assertIn("result=no_speech_timeout", log_output)

    def test_synchronized_ack_handoff_supports_optional_vad_gate(self):
        logger = logging.getLogger("tests.state_machine.synchronized_ack_vad")
        boundary = _PostAckBoundaryResult(
            False, 0, (), (QUIET_CHUNK,), 0.0, 0, 0, 0, False, synchronized=True
        )
        machine = self._machine_for_armed_test(
            FakeAudioSource([LOUD_CHUNK] * 8, fallback_chunk=QUIET_CHUNK),
            logger=logger,
            ack_guard_enabled=True,
            armed_baseline_seconds=0.16,
            armed_baseline_min_chunks=2,
            armed_voice_window_seconds=0.16,
            armed_voice_required_ratio=0.50,
            armed_vad_required_ratio=0.75,
            armed_vad_min_frames=2,
            vad_detector=FakeVadDetector(1.0),
        )

        with self.assertLogs(logger, level="INFO") as logs:
            chunks = machine._wait_for_armed_speech(
                initial_noise_seed=boundary.noise_seed_chunks,
                post_ack_boundary=boundary,
            )

        self.assertIsNotNone(chunks)
        log_output = "\n".join(logs.output)
        self.assertIn("vad_ok=true", log_output)
        self.assertIn("post_ack_synchronized=true", log_output)
        self.assertIn("post_ack_boundary_ready=true", log_output)

    def test_synchronized_ack_handoff_is_stable_for_five_fake_loops(self):
        for loop_number in range(5):
            with self.subTest(loop_number=loop_number), tempfile.TemporaryDirectory() as tmp_dir:
                ack_path = Path(tmp_dir) / "ack.mp3"
                ack_path.write_bytes(b"ack")
                machine = VoiceAssistantStateMachine(
                    settings=make_settings(
                        wake_acknowledgement_enabled=True,
                        wake_acknowledgement_audio_path=str(ack_path),
                        ack_guard_enabled=True,
                        armed_baseline_seconds=0.30,
                        armed_baseline_min_chunks=3,
                        armed_voice_window_seconds=0.30,
                        armed_voice_required_ratio=0.75,
                        post_playback_wake_cooldown_seconds=0,
                        post_playback_quiet_seconds=0,
                    ),
                    audio_source=FakeAudioSource(
                        [WAKE_CHUNK, WAKE_CHUNK, QUIET_CHUNK, LOUD_CHUNK, *SPEECH_CHUNKS],
                        fallback_chunk=QUIET_CHUNK,
                    ),
                    wake_detector=FakeWakeDetector(),
                    openai_client=FakeOpenAIClient(transcription="一加一等于几"),
                    player=FakeAsyncPlayer(running_polls=2),
                    record_audio=fake_record_audio,
                    input_path=Path(tmp_dir) / "input.wav",
                    output_path=Path(tmp_dir) / "output.mp3",
                )

                result = machine.run_once()

            self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
            self.assertEqual(result.transcription, "一加一等于几")
            self.assertFalse(result.cancelled)

    def test_ack_playback_drains_microphone_until_process_completion(self):
        logger = logging.getLogger("tests.state_machine.ack_playback_drain")
        audio_source = FakeAudioSource(
            [LOUD_CHUNK, b"overflow", CLIPPED_CHUNK, QUIET_CHUNK],
            fallback_chunk=QUIET_CHUNK,
        )
        player = FakeAsyncPlayer(running_polls=3)

        with tempfile.TemporaryDirectory() as tmp_dir:
            ack_path = Path(tmp_dir) / "ack.mp3"
            ack_path.write_bytes(b"ack")
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=str(ack_path),
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(),
                player=player,
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                machine._play_wake_acknowledgement()

        self.assertEqual(player.started, [ack_path])
        self.assertEqual(player.handle.wait_calls, 1)
        self.assertEqual(len(audio_source.read_chunks), 3)
        self.assertEqual(audio_source.read_chunk(), QUIET_CHUNK)
        log_output = "\n".join(logs.output)
        self.assertIn("playback microphone drain drained_chunks=3", log_output)
        self.assertIn("overflow_chunks=1", log_output)
        self.assertIn("clipped_chunks=1", log_output)
        self.assertIn("max_peak=32767", log_output)
        self.assertIn("completed=true", log_output)
        self.assertIn("failure_stage=none", log_output)
        self.assertIn("synchronized=false", log_output)

    def test_synchronized_ack_without_noise_seed_fails_closed(self):
        logger = logging.getLogger("tests.state_machine.synchronized_ack_no_noise")
        boundary = _PostAckBoundaryResult(
            False, 0, (LOUD_CHUNK,), (), 0.0, 0, 0, 0, False, synchronized=True
        )
        machine = self._machine_for_armed_test(
            FakeAudioSource([LOUD_CHUNK] * 5, fallback_chunk=QUIET_CHUNK),
            logger=logger,
            ack_guard_enabled=True,
            armed_no_speech_timeout_seconds=0.40,
            armed_baseline_seconds=0.16,
            armed_baseline_min_chunks=2,
            armed_voice_window_seconds=0.16,
            armed_voice_required_ratio=0.50,
        )

        with self.assertLogs(logger, level="INFO") as logs:
            chunks = machine._wait_for_armed_speech(post_ack_boundary=boundary)

        self.assertIsNone(chunks)
        self.assertIn("noise_floor_has_samples=false", "\n".join(logs.output))

    def test_transcription_removes_exact_acknowledgement_prefix_when_question_remains(self):
        machine = self._machine_for_armed_test(
            FakeAudioSource(),
            logger=logging.getLogger("tests.state_machine.ack_prefix"),
            wake_acknowledgement_text="嗯",
        )

        cleaned, removed = machine._remove_acknowledgement_prefix("嗯，一加一等于几")
        phonetic_cleaned, phonetic_removed = machine._remove_acknowledgement_prefix("n一加一等于几")
        ack_only, ack_only_removed = machine._remove_acknowledgement_prefix("嗯。")
        english, english_removed = machine._remove_acknowledgement_prefix("never mind")

        self.assertEqual(cleaned, "一加一等于几")
        self.assertTrue(removed)
        self.assertEqual(phonetic_cleaned, "一加一等于几")
        self.assertTrue(phonetic_removed)
        self.assertEqual(ack_only, "嗯。")
        self.assertFalse(ack_only_removed)
        self.assertEqual(english, "never mind")
        self.assertFalse(english_removed)

    def test_ack_playback_read_failure_joins_process_and_logs_failure_metrics(self):
        logger = logging.getLogger("tests.state_machine.ack_playback_read_failure")

        class FailingAudioSource(FakeAudioSource):
            def read_chunk(self):
                if self.read_chunks:
                    raise RuntimeError("microphone read failed")
                return super().read_chunk()

        audio_source = FailingAudioSource([LOUD_CHUNK])
        player = FakeAsyncPlayer(running_polls=2)
        machine = VoiceAssistantStateMachine(
            settings=make_settings(wake_acknowledgement_enabled=True),
            audio_source=audio_source,
            wake_detector=FakeWakeDetector(),
            openai_client=FakeOpenAIClient(),
            player=player,
            logger=logger,
        )

        with self.assertLogs(logger, level="INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "microphone read failed"):
                machine._play_wake_acknowledgement()

        self.assertEqual(player.handle.wait_calls, 1)
        log_output = "\n".join(logs.output)
        self.assertIn("drained_chunks=1", log_output)
        self.assertIn("completed=false", log_output)
        self.assertIn("failure_stage=drain", log_output)
        self.assertIn("synchronized=false", log_output)

    def test_ack_playback_wait_failure_logs_failure_state(self):
        logger = logging.getLogger("tests.state_machine.ack_playback_wait_failure")
        player = FakeAsyncPlayer(running_polls=1, wait_error=RuntimeError("afplay failed"))
        machine = VoiceAssistantStateMachine(
            settings=make_settings(wake_acknowledgement_enabled=True),
            audio_source=FakeAudioSource([LOUD_CHUNK]),
            wake_detector=FakeWakeDetector(),
            openai_client=FakeOpenAIClient(),
            player=player,
            logger=logger,
        )

        with self.assertLogs(logger, level="INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "afplay failed"):
                machine._play_wake_acknowledgement()

        self.assertEqual(player.handle.wait_calls, 1)
        log_output = "\n".join(logs.output)
        self.assertIn("completed=false", log_output)
        self.assertIn("failure_stage=wait", log_output)
        self.assertIn("synchronized=false", log_output)

    def test_ack_drain_overflow_uses_conservative_post_ack_fallback(self):
        logger = logging.getLogger("tests.state_machine.ack_overflow_fallback")
        audio_source = FakeAudioSource(
            [
                WAKE_CHUNK,
                WAKE_CHUNK,
                b"overflow",
                QUIET_CHUNK,
                QUIET_CHUNK,
                *SPEECH_CHUNKS,
            ],
            fallback_chunk=QUIET_CHUNK,
        )
        player = FakeAsyncPlayer(running_polls=1)

        with tempfile.TemporaryDirectory() as tmp_dir:
            ack_path = Path(tmp_dir) / "ack.mp3"
            ack_path.write_bytes(b"ack")
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=str(ack_path),
                    ack_guard_enabled=True,
                    ack_guard_min_quiet_seconds=0.16,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(),
                player=player,
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        log_output = "\n".join(logs.output)
        self.assertIn("completed=true failure_stage=none synchronized=false", log_output)
        self.assertIn("waiting for safe post-ACK boundary", log_output)
        self.assertIn("post_ack_synchronized=false", log_output)
        self.assertIn("post_ack_suppressed_chunks=2", log_output)

    def _machine_for_armed_test(self, audio_source, *, logger, **setting_overrides):
        vad_detector = setting_overrides.pop("vad_detector", None)
        return VoiceAssistantStateMachine(
            settings=make_settings(**setting_overrides),
            audio_source=audio_source,
            wake_detector=FakeWakeDetector(),
            openai_client=FakeOpenAIClient(),
            player=FakePlayer(),
            logger=logger,
            vad_detector=vad_detector,
        )

    def test_wake_acknowledgement_plays_and_drains_before_recording(self):
        logger = logging.getLogger("tests.state_machine.acknowledgement")
        audio_source = FakeAudioSource([WAKE_CHUNK, WAKE_CHUNK, QUIET_CHUNK, *SPEECH_CHUNKS])
        wake_detector = FakeWakeDetector()
        openai_client = FakeOpenAIClient()
        player = FakePlayer()
        recorded_first_chunk = []

        def record_after_ack_drain(source, *, sample_rate, output_path, **kwargs):
            recorded_first_chunk.append(source.read_chunk())
            return fake_record_audio(source, sample_rate=sample_rate, output_path=output_path, **kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.wav"
            output_path = Path(tmp_dir) / "output.mp3"
            acknowledgement_path = Path(tmp_dir) / "ack.mp3"
            acknowledgement_path.write_bytes(b"ack")
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=acknowledgement_path,
                    wake_acknowledgement_drain_seconds=0.08,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=wake_detector,
                openai_client=openai_client,
                player=player,
                record_audio=record_after_ack_drain,
                input_path=input_path,
                output_path=output_path,
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(player.played, [acknowledgement_path, output_path])
        self.assertEqual(recorded_first_chunk, [LOUD_CHUNK])
        self.assertEqual(openai_client.tts_calls, 1)
        log_output = "\n".join(logs.output)
        self.assertIn("Transition WAIT_WAKE -> ACK_PLAYING", log_output)
        self.assertIn("State ACK_PLAYING: played wake acknowledgement", log_output)
        self.assertIn("discarded 1 acknowledgement microphone chunks", log_output)
        self.assertIn("Transition ACK_PLAYING -> ARMED", log_output)
        self.assertIn("Transition ARMED -> RECORDING", log_output)

    def test_recording_uses_configured_silence_threshold(self):
        audio_source = FakeAudioSource([WAKE_CHUNK, WAKE_CHUNK, *SPEECH_CHUNKS])
        captured_kwargs = {}

        def record_with_capture(source, *, sample_rate, output_path, **kwargs):
            captured_kwargs.update(kwargs)
            return fake_record_audio(source, sample_rate=sample_rate, output_path=output_path, **kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    recording_silence_rms=875,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(),
                player=FakePlayer(),
                record_audio=record_with_capture,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
            )

            result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(captured_kwargs["silence_threshold"], 875)

    def test_no_speech_after_wake_cancels_before_recording_or_openai(self):
        logger = logging.getLogger("tests.state_machine.armed_no_speech")
        audio_source = FakeAudioSource([WAKE_CHUNK, WAKE_CHUNK, QUIET_CHUNK, QUIET_CHUNK], fallback_chunk=QUIET_CHUNK)
        openai_client = FakeOpenAIClient()
        player = FakePlayer()
        history = []

        def fail_record_audio(*args, **kwargs):
            raise AssertionError("recording should not start when ARMED hears no speech")

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    armed_no_speech_timeout_seconds=0.16,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                history=history,
                record_audio=fail_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "no_speech_after_wake")
        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertIsNone(openai_client.transcribed_path)
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [])
        self.assertEqual(history, [])
        log_output = "\n".join(logs.output)
        self.assertIn("Transition WAIT_WAKE -> ARMED", log_output)
        self.assertIn("armed_summary duration_pcm=0.16s chunks=2 valid_chunks=2", log_output)
        self.assertIn("max_rms=0.0 max_peak=0 overflow_chunks=0 voiced_chunks=0 threshold=750.0", log_output)
        self.assertIn("pre_roll_ms=160 pre_roll_chunks=2 pre_roll_overflow_chunks=0", log_output)
        self.assertIn("result=no_speech_timeout", log_output)
        self.assertIn("local cancellation reason=no_speech_after_wake", log_output)

    def test_armed_requires_baseline_before_trigger(self):
        logger = logging.getLogger("tests.state_machine.armed_baseline")
        audio_source = FakeAudioSource([LOUD_CHUNK] * 5)
        machine = self._machine_for_armed_test(
            audio_source,
            logger=logger,
            armed_baseline_seconds=0.40,
            armed_baseline_min_chunks=3,
            armed_pre_roll_seconds=0.50,
        )

        with self.assertLogs(logger, level="INFO") as logs:
            chunks = machine._wait_for_armed_speech()

        self.assertEqual(chunks, tuple([LOUD_CHUNK] * 5))
        log_output = "\n".join(logs.output)
        self.assertIn("armed_trigger", log_output)
        self.assertIn("baseline_ready=true", log_output)
        self.assertIn("baseline_chunks=5", log_output)
        self.assertNotIn("baseline_ready=false", log_output)

    def test_armed_vad_rejects_high_rms_non_voice(self):
        logger = logging.getLogger("tests.state_machine.armed_vad_reject")
        openai_client = FakeOpenAIClient()
        player = FakePlayer()

        def fail_record(*args, **kwargs):
            raise AssertionError("VAD-rejected noise must not start recording")

        machine = VoiceAssistantStateMachine(
            settings=make_settings(armed_no_speech_timeout_seconds=0.80),
            audio_source=FakeAudioSource(
                [WAKE_CHUNK, WAKE_CHUNK, *([QUIET_CHUNK] * 4), *([LOUD_CHUNK] * 8)],
                fallback_chunk=LOUD_CHUNK,
            ),
            wake_detector=FakeWakeDetector(),
            openai_client=openai_client,
            player=player,
            record_audio=fail_record,
            logger=logger,
            vad_detector=FakeVadDetector(0.0),
        )

        with self.assertLogs(logger, level="INFO") as logs:
            result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "no_speech_after_wake")
        self.assertIsNone(openai_client.transcribed_path)
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [])
        log_output = "\n".join(logs.output)
        self.assertIn("armed_summary", log_output)
        self.assertIn("vad_ok=false", log_output)
        self.assertIn("max_vad_ratio=0.000", log_output)

    def test_armed_vad_allows_voice_when_energy_and_vad_pass(self):
        logger = logging.getLogger("tests.state_machine.armed_vad_allow")
        machine = self._machine_for_armed_test(
            FakeAudioSource([QUIET_CHUNK] * 4 + [LOUD_CHUNK] * 4),
            logger=logger,
            vad_detector=FakeVadDetector(1.0),
        )

        with self.assertLogs(logger, level="INFO") as logs:
            chunks = machine._wait_for_armed_speech()

        self.assertIsNotNone(chunks)
        log_output = "\n".join(logs.output)
        self.assertIn("armed_trigger", log_output)
        self.assertIn("energy_ok=true", log_output)
        self.assertIn("vad_ratio=1.000", log_output)
        self.assertIn("vad_ok=true", log_output)

    def test_vad_disabled_preserves_existing_armed_behavior(self):
        logger = logging.getLogger("tests.state_machine.armed_vad_disabled")
        machine = self._machine_for_armed_test(
            FakeAudioSource([LOUD_CHUNK] * 4),
            logger=logger,
        )
        with self.assertLogs(logger, level="INFO") as logs:
            chunks = machine._wait_for_armed_speech()
        self.assertEqual(chunks, tuple([LOUD_CHUNK] * 4))
        self.assertIn("vad_ratio=disabled", "\n".join(logs.output))

    def test_no_speech_after_wake_does_not_record_with_cold_noise_floor(self):
        logger = logging.getLogger("tests.state_machine.cold_noise_floor")
        audio_source = FakeAudioSource(
            [WAKE_CHUNK, WAKE_CHUNK, MODERATE_CHUNK, MODERATE_CHUNK, MODERATE_CHUNK, QUIET_CHUNK],
            fallback_chunk=QUIET_CHUNK,
        )
        openai_client = FakeOpenAIClient()
        player = FakePlayer()

        def fail_record(*args, **kwargs):
            raise AssertionError("record_audio must not be called")

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    armed_no_speech_timeout_seconds=0.64,
                    armed_baseline_seconds=0.30,
                    armed_baseline_min_chunks=3,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fail_record,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )
            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "no_speech_after_wake")
        self.assertIsNone(openai_client.transcribed_path)
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [])
        log_output = "\n".join(logs.output)
        self.assertIn("armed_summary", log_output)
        self.assertIn("result=no_speech_timeout", log_output)
        self.assertNotIn("result=recording_started", log_output)

    def test_armed_last_chunk_must_be_voiced(self):
        logger = logging.getLogger("tests.state_machine.armed_latest_chunk")
        audio_source = FakeAudioSource([LOUD_CHUNK, LOUD_CHUNK, LOUD_CHUNK, QUIET_CHUNK, LOUD_CHUNK])
        machine = self._machine_for_armed_test(
            audio_source,
            logger=logger,
            armed_baseline_seconds=0.30,
            armed_baseline_min_chunks=3,
            armed_last_chunk_must_be_voiced=True,
        )

        with self.assertLogs(logger, level="INFO") as logs:
            chunks = machine._wait_for_armed_speech()

        self.assertIsNotNone(chunks)
        self.assertEqual(len(audio_source.read_chunks), 5)
        self.assertIn("baseline_ready=true", "\n".join(logs.output))

    def test_ack_guard_ack_only_does_not_enter_recording(self):
        logger = logging.getLogger("tests.state_machine.ack_guard_only")
        audio_source = FakeAudioSource(
            [WAKE_CHUNK, WAKE_CHUNK, MODERATE_CHUNK, QUIET_CHUNK, QUIET_CHUNK],
            fallback_chunk=QUIET_CHUNK,
        )
        openai_client = FakeOpenAIClient()
        player = FakePlayer()

        def fail_record(*args, **kwargs):
            raise AssertionError("record_audio must not be called")

        with tempfile.TemporaryDirectory() as tmp_dir:
            acknowledgement_path = Path(tmp_dir) / "ack.mp3"
            acknowledgement_path.write_bytes(b"ack")
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=acknowledgement_path,
                    ack_guard_enabled=True,
                    ack_guard_min_quiet_seconds=0.16,
                    armed_no_speech_timeout_seconds=0.40,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fail_record,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )
            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "no_speech_after_wake")
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [acknowledgement_path])
        self.assertIn("preserved_chunks=0", "\n".join(logs.output))
        self.assertIn("post_ack_quiet_observed=true", "\n".join(logs.output))

    def test_ack_guard_can_preserve_boundary_speech(self):
        logger = logging.getLogger("tests.state_machine.ack_guard_boundary")
        audio_source = FakeAudioSource(
            [
                WAKE_CHUNK,
                WAKE_CHUNK,
                CLIPPED_CHUNK,
                b"overflow",
                QUIET_CHUNK,
                QUIET_CHUNK,
                LOUD_CHUNK,
                USER_CLIPPED_CHUNK,
                LOUD_CHUNK,
                LOUD_CHUNK,
            ],
            fallback_chunk=QUIET_CHUNK,
        )
        preserved_first_chunk = []

        def capture_recording(source, *, sample_rate, output_path, **kwargs):
            for _ in range(4):
                preserved_first_chunk.append(source.read_chunk())
            return fake_record_audio(source, sample_rate=sample_rate, output_path=output_path, **kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            acknowledgement_path = Path(tmp_dir) / "ack.mp3"
            acknowledgement_path.write_bytes(b"ack")
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=acknowledgement_path,
                    ack_guard_enabled=True,
                    ack_guard_min_quiet_seconds=0.16,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(),
                player=FakePlayer(),
                record_audio=capture_recording,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )
            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(
            preserved_first_chunk,
            [LOUD_CHUNK, USER_CLIPPED_CHUNK, LOUD_CHUNK, LOUD_CHUNK],
        )
        self.assertNotIn(CLIPPED_CHUNK, preserved_first_chunk)
        self.assertIn(USER_CLIPPED_CHUNK, preserved_first_chunk)
        self.assertIn("post_ack_quiet_observed=true", "\n".join(logs.output))
        self.assertIn("noise_seed_count=2", "\n".join(logs.output))
        self.assertIn("post_ack_overflow_chunks=1", "\n".join(logs.output))
        self.assertIn("post_ack_clipped_chunks=1", "\n".join(logs.output))

    def test_post_boundary_overflow_is_omitted_without_clearing_safe_pre_roll(self):
        logger = logging.getLogger("tests.state_machine.post_boundary_overflow")
        audio_source = FakeAudioSource(
            [LOUD_CHUNK, b"overflow", LOUD_CHUNK, LOUD_CHUNK, LOUD_CHUNK]
        )
        boundary = _PostAckBoundaryResult(
            True, 2, (), (QUIET_CHUNK, QUIET_CHUNK), 0.0, 0, 0, 0, False
        )
        machine = self._machine_for_armed_test(
            audio_source, logger=logger, ack_guard_enabled=True
        )
        with self.assertLogs(logger, level="INFO"):
            chunks = machine._wait_for_armed_speech(
                initial_noise_seed=boundary.noise_seed_chunks,
                post_ack_boundary=boundary,
            )
        self.assertEqual(chunks, tuple([LOUD_CHUNK] * 3))

    def test_ack_guard_without_quiet_does_not_enter_recording(self):
        logger = logging.getLogger("tests.state_machine.ack_no_quiet")
        audio_source = FakeAudioSource(
            [WAKE_CHUNK, WAKE_CHUNK, CLIPPED_CHUNK, b"overflow", LOUD_CHUNK, LOUD_CHUNK],
            fallback_chunk=LOUD_CHUNK,
        )
        openai_client = FakeOpenAIClient()
        player = FakePlayer()

        def fail_record(*args, **kwargs):
            raise AssertionError("record_audio must not be called without a safe post-ACK boundary")

        with tempfile.TemporaryDirectory() as tmp_dir:
            acknowledgement_path = Path(tmp_dir) / "ack.mp3"
            acknowledgement_path.write_bytes(b"ack")
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=acknowledgement_path,
                    ack_guard_enabled=True,
                    ack_guard_min_quiet_seconds=0.16,
                    ack_guard_max_buffer_seconds=0.32,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fail_record,
                logger=logger,
            )
            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "no_speech_after_wake")
        self.assertIsNone(openai_client.transcribed_path)
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        log_output = "\n".join(logs.output)
        self.assertIn("post_ack_quiet_observed=false", log_output)
        self.assertIn("timed_out=true", log_output)
        self.assertNotIn("result=recording_started", log_output)

    def test_ack_disabled_still_allows_immediate_speech(self):
        logger = logging.getLogger("tests.state_machine.ack_disabled_immediate")
        audio_source = FakeAudioSource([WAKE_CHUNK, WAKE_CHUNK, *SPEECH_CHUNKS])
        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=False,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(),
                player=FakePlayer(),
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )
            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()
        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        log_output = "\n".join(logs.output)
        self.assertIn("result=recording_started", log_output)
        self.assertIn("post_ack_quiet_observed=true", log_output)

    def test_zero_post_ack_quiet_requirement_fails_closed(self):
        machine = self._machine_for_armed_test(
            FakeAudioSource([LOUD_CHUNK], fallback_chunk=LOUD_CHUNK),
            logger=logging.getLogger("tests.state_machine.zero_ack_quiet"),
        )
        machine.settings = make_settings(
            wake_acknowledgement_enabled=True,
            ack_guard_enabled=True,
            ack_guard_min_quiet_seconds=0,
        )
        boundary = machine._wait_for_post_ack_boundary()
        self.assertTrue(boundary.timed_out)
        self.assertFalse(boundary.quiet_observed)
        self.assertEqual(boundary.noise_seed_chunks, ())

    def test_armed_trigger_preserves_pre_roll_chunks(self):
        logger = logging.getLogger("tests.state_machine.armed_pre_roll")
        audio_source = FakeAudioSource(
            [WAKE_CHUNK, WAKE_CHUNK, QUIET_CHUNK, QUIET_CHUNK, LOUD_CHUNK, LOUD_CHUNK, LOUD_CHUNK],
            fallback_chunk=LOUD_CHUNK,
        )
        recorded_chunks = []

        def record_with_pre_roll_capture(source, *, sample_rate, output_path, **kwargs):
            for _ in range(5):
                recorded_chunks.append(source.read_chunk())
            return fake_record_audio(source, sample_rate=sample_rate, output_path=output_path, **kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    armed_pre_roll_seconds=0.5,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(),
                player=FakePlayer(),
                record_audio=record_with_pre_roll_capture,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(recorded_chunks, [QUIET_CHUNK, QUIET_CHUNK, LOUD_CHUNK, LOUD_CHUNK, LOUD_CHUNK])
        log_output = "\n".join(logs.output)
        self.assertIn("armed_trigger after=0.40s", log_output)
        self.assertIn("duration_pcm=0.40s chunks=5 valid_chunks=5", log_output)
        self.assertIn("max_rms=2000.0 max_peak=2000 overflow_chunks=0 voiced_chunks=3", log_output)
        self.assertIn("voiced_window=3/4", log_output)
        self.assertIn("pre_roll_ms=400", log_output)
        self.assertIn("pre_roll_chunks=5", log_output)
        self.assertIn("pre_roll_overflow_chunks=0 result=recording_started", log_output)

    def test_armed_dynamic_threshold_rejects_noise_floor_scaled_chunks(self):
        logger = logging.getLogger("tests.state_machine.armed_dynamic_threshold")
        audio_source = FakeAudioSource(
            [WAKE_CHUNK, WAKE_CHUNK, NOISE_CHUNK, NOISE_CHUNK, MODERATE_CHUNK, MODERATE_CHUNK],
            fallback_chunk=MODERATE_CHUNK,
        )
        openai_client = FakeOpenAIClient()

        def fail_record_audio(*args, **kwargs):
            raise AssertionError("recording should not start below the dynamic threshold")

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    armed_no_speech_timeout_seconds=0.32,
                    armed_min_rms=500,
                    armed_snr_multiplier=2.5,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=FakePlayer(),
                record_audio=fail_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "no_speech_after_wake")
        self.assertIsNone(openai_client.transcribed_path)
        log_output = "\n".join(logs.output)
        self.assertIn("armed_summary", log_output)
        self.assertIn("max_rms=800.0", log_output)
        self.assertIn("dynamic_threshold=1500.0", log_output)
        self.assertIn("noise_floor=600.0", log_output)

    def test_armed_rejects_overflow_and_clipped_chunks(self):
        logger = logging.getLogger("tests.state_machine.armed_overflow_clipped")
        audio_source = FakeAudioSource(
            [WAKE_CHUNK, WAKE_CHUNK, b"overflow", CLIPPED_CHUNK, CLIPPED_CHUNK, CLIPPED_CHUNK],
            fallback_chunk=CLIPPED_CHUNK,
        )

        def fail_record_audio(*args, **kwargs):
            raise AssertionError("recording should not start from overflowed or clipped chunks")

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    armed_no_speech_timeout_seconds=0.32,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(),
                player=FakePlayer(),
                record_audio=fail_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        log_output = "\n".join(logs.output)
        self.assertIn("ignoring overflowed microphone chunk", log_output)
        self.assertIn("overflow_chunks=1", log_output)
        self.assertIn("max_peak=32767", log_output)
        self.assertIn("voiced_chunks=0", log_output)

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
        self.assertIn("Transition WAIT_WAKE -> ARMED", log_output)
        self.assertIn("Transition ARMED -> RECORDING", log_output)
        self.assertIn("Transition PLAYING -> WAIT_WAKE", log_output)
        self.assertIn("suppressing post-playback wake detection", log_output)

    def test_silent_recording_cancels_before_transcription(self):
        logger = logging.getLogger("tests.state_machine.silent_recording")
        openai_client = FakeOpenAIClient()
        player = FakePlayer()

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=FakeAudioSource(),
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fake_silent_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "silent_recording")
        self.assertIsNone(openai_client.transcribed_path)
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [])
        self.assertIn("local cancellation reason=silent_recording", "\n".join(logs.output))

    def test_cancel_and_filler_transcripts_do_not_generate_answer(self):
        for transcription, expected_reason in (
            ("", "empty_transcript"),
            ("um", "filler_transcript"),
            ("取消", "cancel_phrase"),
            ("never mind", "cancel_phrase"),
        ):
            with self.subTest(transcription=transcription):
                logger = logging.getLogger(f"tests.state_machine.transcript_cancel.{expected_reason}")
                openai_client = FakeOpenAIClient(transcription=transcription)
                player = FakePlayer()
                history = []

                with tempfile.TemporaryDirectory() as tmp_dir:
                    machine = VoiceAssistantStateMachine(
                        settings=make_settings(
                            post_playback_wake_cooldown_seconds=0,
                            post_playback_quiet_seconds=0,
                        ),
                        audio_source=FakeAudioSource(),
                        wake_detector=FakeWakeDetector(),
                        openai_client=openai_client,
                        player=player,
                        history=history,
                        record_audio=fake_record_audio,
                        input_path=Path(tmp_dir) / "input.wav",
                        output_path=Path(tmp_dir) / "output.mp3",
                        logger=logger,
                    )

                    with self.assertLogs(logger, level="INFO") as logs:
                        result = machine.run_once()

                self.assertTrue(result.cancelled)
                self.assertEqual(result.cancellation_reason, expected_reason)
                self.assertEqual(result.answer, "")
                self.assertEqual(openai_client.chat_calls, 0)
                self.assertEqual(openai_client.tts_calls, 0)
                self.assertEqual(player.played, [])
                self.assertEqual(history, [])
                self.assertIn(f"local cancellation reason={expected_reason}", "\n".join(logs.output))

    def test_noisy_cancel_transcripts_do_not_generate_answer(self):
        examples = (
            ("没事", "exact"),
            ("没事了", "noisy_suffix"),
            ("没事不用了", "noisy_suffix"),
            ("没事 谢谢", "noisy_suffix"),
            ("没事 后面有声音", "noisy_suffix"),
            ("取消吧", "noisy_suffix"),
            ("算了算了", "noisy_suffix"),
            ("stop", "exact"),
            ("stop please", "noisy_suffix"),
            ("cancel", "exact"),
            ("cancel that", "noisy_suffix"),
            ("never mind", "exact"),
            ("不用了", "exact"),
            ("不用啦", "colloquial_variant"),
            ("不用不用", "colloquial_variant"),
            ("不用不用了", "colloquial_variant"),
            ("不用了谢谢", "noisy_suffix"),
            ("不要了", "colloquial_variant"),
            ("没事儿", "noisy_suffix"),
            ("没事没事儿", "noisy_suffix"),
            ("没事儿没事儿", "noisy_suffix"),
        )
        for transcription, expected_mode in examples:
            with self.subTest(transcription=transcription):
                logger = logging.getLogger(f"tests.state_machine.noisy_cancel.{expected_mode}")
                openai_client = FakeOpenAIClient(transcription=transcription)
                player = FakePlayer()
                history = []

                with tempfile.TemporaryDirectory() as tmp_dir:
                    machine = VoiceAssistantStateMachine(
                        settings=make_settings(
                            post_playback_wake_cooldown_seconds=0,
                            post_playback_quiet_seconds=0,
                        ),
                        audio_source=FakeAudioSource(),
                        wake_detector=FakeWakeDetector(),
                        openai_client=openai_client,
                        player=player,
                        history=history,
                        record_audio=fake_record_audio,
                        input_path=Path(tmp_dir) / "input.wav",
                        output_path=Path(tmp_dir) / "output.mp3",
                        logger=logger,
                    )

                    with self.assertLogs(logger, level="INFO") as logs:
                        result = machine.run_once()

                log_output = "\n".join(logs.output)
                self.assertTrue(result.cancelled)
                self.assertEqual(result.cancellation_reason, "cancel_phrase")
                self.assertEqual(result.answer, "")
                self.assertEqual(openai_client.chat_calls, 0)
                self.assertEqual(openai_client.tts_calls, 0)
                self.assertEqual(player.played, [])
                self.assertEqual(history, [])
                self.assertIn("transcript cancellation normalized_transcript=", log_output)
                self.assertIn(f"match_mode={expected_mode}", log_output)
                self.assertIn("local cancellation reason=cancel_phrase", log_output)

    def test_cancel_prefixed_commands_are_not_locally_cancelled(self):
        examples = (
            "不用了帮我查天气",
            "没事的话帮我查天气",
            "取消我明天的闹钟",
            "不要取消我明天的闹钟",
            "cancel my alarm tomorrow",
        )
        for transcription in examples:
            with self.subTest(transcription=transcription):
                logger = logging.getLogger("tests.state_machine.cancel_guard")
                openai_client = FakeOpenAIClient(transcription=transcription)
                player = FakePlayer()
                history = []

                with tempfile.TemporaryDirectory() as tmp_dir:
                    input_path = Path(tmp_dir) / "input.wav"
                    output_path = Path(tmp_dir) / "output.mp3"
                    machine = VoiceAssistantStateMachine(
                        settings=make_settings(
                            post_playback_wake_cooldown_seconds=0,
                            post_playback_quiet_seconds=0,
                        ),
                        audio_source=FakeAudioSource(),
                        wake_detector=FakeWakeDetector(),
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

                log_output = "\n".join(logs.output)
                self.assertFalse(result.cancelled)
                self.assertEqual(result.transcription, transcription)
                self.assertEqual(result.answer, "Two plus two is four.")
                self.assertEqual(openai_client.chat_calls, 1)
                self.assertEqual(openai_client.tts_calls, 1)
                self.assertEqual(player.played, [output_path])
                self.assertEqual(history[0], {"role": "user", "content": transcription})
                self.assertNotIn("transcript cancellation normalized_transcript=", log_output)
                self.assertNotIn("local cancellation reason=cancel_phrase", log_output)

    def test_short_non_cancel_transcript_logs_safe_match_decision(self):
        logger = logging.getLogger("tests.state_machine.cancel_diagnostic")
        transcription = "不用了帮我查天气"
        openai_client = FakeOpenAIClient(transcription=transcription)
        player = FakePlayer()
        history = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.mp3"
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=FakeAudioSource(),
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                history=history,
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=output_path,
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        log_output = "\n".join(logs.output)
        self.assertFalse(result.cancelled)
        self.assertEqual(openai_client.chat_calls, 1)
        self.assertEqual(openai_client.tts_calls, 1)
        self.assertEqual(player.played, [output_path])
        self.assertEqual(history[0], {"role": "user", "content": transcription})
        self.assertIn("transcript cancellation check normalized_transcript='不用了帮我查天气'", log_output)
        self.assertIn("compact_transcript='不用了帮我查天气'", log_output)
        self.assertIn("match_decision=not_cancelled", log_output)
        self.assertNotIn("local cancellation reason=cancel_phrase", log_output)

    def test_tool_route_answers_calculator_without_chat_history(self):
        logger = logging.getLogger("tests.state_machine.tools")
        audio_source = FakeAudioSource()
        wake_detector = FakeWakeDetector()
        openai_client = FakeOpenAIClient()
        player = FakePlayer()
        history = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.wav"
            output_path = Path(tmp_dir) / "output.mp3"
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    enable_tools=True,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
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
            synthesized_text = output_path.read_text(encoding="utf-8")

        self.assertEqual(result.answer, "The answer is 4.")
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 1)
        self.assertEqual(history, [])
        self.assertEqual(synthesized_text, "The answer is 4.")
        self.assertIn("tool route=calculator status=success", "\n".join(logs.output))

    def test_traditional_chinese_local_tool_routes_skip_chat_history(self):
        cases = (
            ("現在幾點了", "The local time is", "tool route=time status=success"),
            ("100減20是多少", "The answer is 80.", "tool route=calculator status=success"),
        )

        for transcription, expected_answer, expected_log in cases:
            with self.subTest(transcription=transcription):
                logger = logging.getLogger(f"tests.state_machine.traditional.{transcription}")
                audio_source = FakeAudioSource()
                wake_detector = FakeWakeDetector()
                openai_client = FakeOpenAIClient(transcription=transcription)
                player = FakePlayer()
                history = []

                with tempfile.TemporaryDirectory() as tmp_dir:
                    input_path = Path(tmp_dir) / "input.wav"
                    output_path = Path(tmp_dir) / "output.mp3"
                    machine = VoiceAssistantStateMachine(
                        settings=make_settings(
                            enable_tools=True,
                            post_playback_wake_cooldown_seconds=0,
                            post_playback_quiet_seconds=0,
                        ),
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
                    synthesized_text = output_path.read_text(encoding="utf-8")

                self.assertIn(expected_answer, result.answer)
                self.assertEqual(openai_client.chat_calls, 0)
                self.assertEqual(openai_client.tts_calls, 1)
                self.assertEqual(history, [])
                self.assertIn(expected_answer, synthesized_text)
                self.assertIn(expected_log, "\n".join(logs.output))

    def test_provider_error_logs_route_params_and_result_data(self):
        logger = logging.getLogger("tests.state_machine.provider_error")
        route = ToolRoute(
            "weather",
            "weather_provider",
            {"query": "今天这里天气怎么样", "intent": "today"},
            "weather request",
        )
        result = ToolResult(
            "error",
            "weather provider error: no_location_match",
            "I could not get weather data: Open-Meteo found no location match.",
            {
                "category": "weather",
                "query": "今天这里天气怎么样",
                "intent": "today",
                "attempted_location": "Singapore",
                "location_source": "default",
                "provider_error": "no_location_match",
                "status_code": "",
            },
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.mp3"
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    enable_tools=True,
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                ),
                audio_source=FakeAudioSource(),
                wake_detector=FakeWakeDetector(),
                openai_client=FakeOpenAIClient(transcription="今天这里天气怎么样"),
                player=FakePlayer(),
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=output_path,
                logger=logger,
            )

            with patch("src.state_machine.answer_with_tools", return_value=(result.answer, route, result)):
                with self.assertLogs(logger, level="INFO") as logs:
                    loop_result = machine.run_once()

        self.assertEqual(loop_result.answer, result.answer)
        log_output = "\n".join(logs.output)
        self.assertIn("tool route=weather status=error", log_output)
        self.assertIn("params={'query': '今天这里天气怎么样', 'intent': 'today'}", log_output)
        self.assertIn("'attempted_location': 'Singapore'", log_output)
        self.assertIn("'provider_error': 'no_location_match'", log_output)
        self.assertNotIn("sk-test", log_output)

    def test_single_wake_candidate_does_not_enter_recording_until_confirmed(self):
        logger = logging.getLogger("tests.state_machine.wake_confirmation")
        audio_source = FakeAudioSource([WAKE_CHUNK, QUIET_CHUNK, WAKE_CHUNK, WAKE_CHUNK, *SPEECH_CHUNKS])
        wake_detector = FakeWakeDetector()

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                    wake_confirmation_frames=2,
                ),
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
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(wake_detector.detected_chunks, [WAKE_CHUNK, QUIET_CHUNK, WAKE_CHUNK, WAKE_CHUNK])
        log_output = "\n".join(logs.output)
        self.assertIn("wake word candidate 1/2", log_output)
        self.assertIn("State WAIT_WAKE: wake word detected", log_output)

    def test_post_playback_residue_is_drained_without_wake_detection(self):
        logger = logging.getLogger("tests.state_machine.post_playback")
        audio_source = FakeAudioSource([WAKE_CHUNK, WAKE_CHUNK, *SPEECH_CHUNKS, b"overflow", WAKE_CHUNK, QUIET_CHUNK])
        wake_detector = FakeWakeDetector()

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    post_playback_wake_cooldown_seconds=0.16,
                    post_playback_quiet_seconds=0.08,
                    wake_confirmation_frames=2,
                ),
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
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(wake_detector.detected_chunks, [WAKE_CHUNK, WAKE_CHUNK, QUIET_CHUNK])
        self.assertGreaterEqual(audio_source.read_chunks.count(b"overflow"), 1)
        log_output = "\n".join(logs.output)
        self.assertIn("suppressing post-playback wake detection", log_output)
        self.assertIn("discarded", log_output)
        self.assertIn("post-playback quiet gate consumed", log_output)

    def test_post_playback_residue_after_cooldown_waits_for_quiet_gate(self):
        logger = logging.getLogger("tests.state_machine.post_playback_quiet")
        audio_source = FakeAudioSource(
            [
                WAKE_CHUNK,
                WAKE_CHUNK,
                *SPEECH_CHUNKS,
                WAKE_CHUNK,
                WAKE_CHUNK,
                QUIET_CHUNK,
                QUIET_CHUNK,
            ],
            fallback_chunk=QUIET_CHUNK,
        )
        wake_detector = FakeWakeDetector()
        player = FakePlayer()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.mp3"
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    post_playback_wake_cooldown_seconds=0.16,
                    post_playback_quiet_seconds=0.16,
                    post_playback_quiet_rms=500,
                    post_playback_max_suppression_seconds=1.0,
                    wake_confirmation_frames=2,
                ),
                audio_source=audio_source,
                wake_detector=wake_detector,
                openai_client=FakeOpenAIClient(),
                player=player,
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=output_path,
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(wake_detector.detected_chunks[:2], [WAKE_CHUNK, WAKE_CHUNK])
        self.assertEqual(player.played, [output_path])
        log_output = "\n".join(logs.output)
        self.assertIn("post-playback quiet gate consumed", log_output)

    def test_transcript_cancel_suppresses_residual_wake_before_later_intentional_wake(self):
        logger = logging.getLogger("tests.state_machine.post_cancel_transcript")
        audio_source = FakeAudioSource(
            [
                WAKE_CHUNK,
                WAKE_CHUNK,
                *SPEECH_CHUNKS,
                WAKE_CHUNK,
                WAKE_CHUNK,
                QUIET_CHUNK,
                QUIET_CHUNK,
                WAKE_CHUNK,
                WAKE_CHUNK,
                *SPEECH_CHUNKS,
            ],
            fallback_chunk=QUIET_CHUNK,
        )
        wake_detector = FakeWakeDetector()
        openai_client = FakeOpenAIClient(transcription="算了算了")
        player = FakePlayer()
        history = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            acknowledgement_path = Path(tmp_dir) / "ack.mp3"
            acknowledgement_path.write_bytes(b"ack")
            output_path = Path(tmp_dir) / "output.mp3"
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    wake_acknowledgement_enabled=True,
                    wake_acknowledgement_audio_path=acknowledgement_path,
                    wake_acknowledgement_drain_seconds=0,
                    post_playback_wake_cooldown_seconds=0.08,
                    post_playback_quiet_seconds=0.16,
                    post_playback_quiet_rms=500,
                    post_playback_max_suppression_seconds=1.0,
                    wake_confirmation_frames=2,
                ),
                audio_source=audio_source,
                wake_detector=wake_detector,
                openai_client=openai_client,
                player=player,
                history=history,
                record_audio=fake_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=output_path,
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as first_logs:
                first_result = machine.run_once()
            consumed_after_cancel = list(audio_source.read_chunks)

            openai_client.transcription = "what is two plus two?"
            with self.assertLogs(logger, level="INFO") as second_logs:
                second_result = machine.run_once()

        self.assertTrue(first_result.cancelled)
        self.assertEqual(first_result.cancellation_reason, "cancel_phrase")
        self.assertEqual(first_result.answer, "")
        self.assertEqual(openai_client.chat_calls, 1)
        self.assertEqual(openai_client.tts_calls, 1)
        self.assertEqual(history[-1], {"role": "assistant", "content": "Two plus two is four."})
        self.assertEqual(second_result.answer, "Two plus two is four.")
        self.assertEqual(player.played, [acknowledgement_path, acknowledgement_path, output_path])
        self.assertEqual(
            consumed_after_cancel,
            [WAKE_CHUNK, WAKE_CHUNK, *SPEECH_CHUNKS, WAKE_CHUNK, WAKE_CHUNK, QUIET_CHUNK, QUIET_CHUNK],
        )
        first_log_output = "\n".join(first_logs.output)
        second_log_output = "\n".join(second_logs.output)
        self.assertIn("transcript cancellation normalized_transcript='算了算了' match_mode=noisy_suffix", first_log_output)
        self.assertIn("suppressing post-cancellation wake detection reason=cancel_phrase", first_log_output)
        self.assertIn("post-cancellation quiet gate consumed", first_log_output)
        self.assertIn("max_suppressed_score=1.000000000", first_log_output)
        self.assertNotIn("Transition WAIT_WAKE -> ACK_PLAYING", first_log_output.split("post-cancellation quiet gate consumed", 1)[1])
        self.assertIn("Transition WAIT_WAKE -> ACK_PLAYING", second_log_output)

    def test_armed_no_speech_cancel_suppresses_residual_wake_chunks(self):
        logger = logging.getLogger("tests.state_machine.post_cancel_no_speech")
        audio_source = FakeAudioSource(
            [
                WAKE_CHUNK,
                WAKE_CHUNK,
                QUIET_CHUNK,
                QUIET_CHUNK,
                WAKE_CHUNK,
                WAKE_CHUNK,
                QUIET_CHUNK,
                QUIET_CHUNK,
            ],
            fallback_chunk=QUIET_CHUNK,
        )
        openai_client = FakeOpenAIClient()
        player = FakePlayer()

        def fail_record_audio(*args, **kwargs):
            raise AssertionError("recording should not start when ARMED hears no speech")

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    armed_no_speech_timeout_seconds=0.16,
                    post_playback_wake_cooldown_seconds=0.08,
                    post_playback_quiet_seconds=0.16,
                    post_playback_quiet_rms=500,
                    post_playback_max_suppression_seconds=1.0,
                    wake_confirmation_frames=2,
                ),
                audio_source=audio_source,
                wake_detector=FakeWakeDetector(),
                openai_client=openai_client,
                player=player,
                record_audio=fail_record_audio,
                input_path=Path(tmp_dir) / "input.wav",
                output_path=Path(tmp_dir) / "output.mp3",
                logger=logger,
            )

            with self.assertLogs(logger, level="INFO") as logs:
                result = machine.run_once()

        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "no_speech_after_wake")
        self.assertIsNone(openai_client.transcribed_path)
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [])
        self.assertEqual(
            audio_source.read_chunks,
            [WAKE_CHUNK, WAKE_CHUNK, QUIET_CHUNK, QUIET_CHUNK, WAKE_CHUNK, WAKE_CHUNK, QUIET_CHUNK, QUIET_CHUNK],
        )
        log_output = "\n".join(logs.output)
        self.assertIn("local cancellation reason=no_speech_after_wake", log_output)
        self.assertIn("suppressing post-cancellation wake detection reason=no_speech_after_wake", log_output)
        self.assertIn("post-cancellation quiet gate consumed", log_output)
        self.assertIn("max_suppressed_score=1.000000000", log_output)

    def test_overflowed_wake_chunk_is_ignored(self):
        logger = logging.getLogger("tests.state_machine.overflow")
        audio_source = FakeAudioSource([b"overflow", WAKE_CHUNK, WAKE_CHUNK, *SPEECH_CHUNKS])
        wake_detector = FakeWakeDetector()

        with tempfile.TemporaryDirectory() as tmp_dir:
            machine = VoiceAssistantStateMachine(
                settings=make_settings(
                    post_playback_wake_cooldown_seconds=0,
                    post_playback_quiet_seconds=0,
                    wake_confirmation_frames=2,
                ),
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
                result = machine.run_once()

        self.assertEqual(result.final_state, AssistantState.WAIT_WAKE)
        self.assertEqual(wake_detector.detected_chunks, [WAKE_CHUNK, WAKE_CHUNK])
        self.assertIn("ignoring overflowed microphone chunk", "\n".join(logs.output))

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

    def test_empty_transcription_cancels_without_chat_tts_or_playback(self):
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
        self.assertTrue(result.cancelled)
        self.assertEqual(result.cancellation_reason, "empty_transcript")
        self.assertEqual(result.transcription, "")
        self.assertEqual(result.answer, "")
        self.assertIsNone(result.error)
        self.assertEqual(openai_client.transcribed_path, input_path)
        self.assertEqual(openai_client.chat_calls, 0)
        self.assertEqual(openai_client.tts_calls, 0)
        self.assertEqual(player.played, [])
        log_output = "\n".join(logs.output)
        self.assertIn("local cancellation reason=empty_transcript", log_output)
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

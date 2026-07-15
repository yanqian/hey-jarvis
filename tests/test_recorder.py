import struct
import tempfile
import unittest
import wave
import logging
from pathlib import Path

from src.recorder import record_to_wav
from src.vad import VadResult


def repeated_sample(sample: int, frames: int) -> bytes:
    return struct.pack(f"<{frames}h", *([sample] * frames))


class SequenceVad:
    is_enabled = True

    def __init__(self, ratios):
        self.ratios = iter(ratios)

    def analyze(self, pcm_chunk, sample_rate):
        ratio = next(self.ratios)
        return VadResult(ratio, round(ratio * 5), 5)


class RecorderTests(unittest.TestCase):
    def test_record_to_wav_stops_on_silence_and_writes_valid_file(self):
        sample_rate = 16000
        chunk_frames = 1600
        speech = repeated_sample(1200, chunk_frames)
        silence = repeated_sample(0, chunk_frames)
        chunks = iter([speech, speech, silence, silence, speech])

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "input.wav"
            result = record_to_wav(
                chunks,
                sample_rate=sample_rate,
                silence_seconds=0.2,
                max_record_seconds=2.0,
                output_path=output_path,
            )

            with wave.open(str(output_path), "rb") as wav_file:
                self.assertEqual(wav_file.getnchannels(), 1)
                self.assertEqual(wav_file.getsampwidth(), 2)
                self.assertEqual(wav_file.getframerate(), sample_rate)
                self.assertEqual(wav_file.getnframes(), chunk_frames * 4)

        self.assertEqual(result.path, output_path)
        self.assertEqual(result.chunks_recorded, 4)
        self.assertEqual(result.stopped_by, "silence")
        self.assertAlmostEqual(result.duration_seconds, 0.4)

    def test_record_to_wav_stops_on_max_duration(self):
        sample_rate = 16000
        chunk_frames = 1600
        speech = repeated_sample(1200, chunk_frames)

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = record_to_wav(
                [speech, speech, speech, speech],
                sample_rate=sample_rate,
                silence_seconds=0.1,
                max_record_seconds=0.25,
                output_path=Path(tmp_dir) / "input.wav",
            )

        self.assertEqual(result.chunks_recorded, 3)
        self.assertEqual(result.stopped_by, "max_duration")
        self.assertAlmostEqual(result.duration_seconds, 0.3)

    def test_record_to_wav_tolerates_occasional_noise_after_speech(self):
        sample_rate = 16000
        chunk_frames = 1600
        speech = repeated_sample(1300, chunk_frames)
        background = repeated_sample(650, chunk_frames)
        short_noise = repeated_sample(900, chunk_frames)
        chunks = [speech, speech, background, background, short_noise, background, background, speech]

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = record_to_wav(
                chunks,
                sample_rate=sample_rate,
                silence_seconds=0.5,
                max_record_seconds=2.0,
                silence_threshold=750,
                output_path=Path(tmp_dir) / "input.wav",
            )

        self.assertEqual(result.chunks_recorded, 7)
        self.assertEqual(result.stopped_by, "silence")
        self.assertAlmostEqual(result.duration_seconds, 0.7)

    def test_record_to_wav_speech_like_chunks_extend_recording(self):
        sample_rate = 16000
        chunk_frames = 1600
        speech = repeated_sample(1300, chunk_frames)
        background = repeated_sample(650, chunk_frames)
        chunks = [speech, background, background, speech, background, background, background, background, background]

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = record_to_wav(
                chunks,
                sample_rate=sample_rate,
                silence_seconds=0.5,
                max_record_seconds=2.0,
                silence_threshold=750,
                output_path=Path(tmp_dir) / "input.wav",
            )

        self.assertEqual(result.chunks_recorded, 9)
        self.assertEqual(result.stopped_by, "silence")
        self.assertAlmostEqual(result.duration_seconds, 0.9)

    def test_invalid_pcm_chunk_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                record_to_wav(
                    [b"\x00"],
                    silence_seconds=0.1,
                    max_record_seconds=1.0,
                    output_path=Path(tmp_dir) / "input.wav",
                )

    def test_negative_silence_threshold_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                record_to_wav(
                    [],
                    silence_threshold=-1,
                    output_path=Path(tmp_dir) / "input.wav",
                )

    def test_recorder_vad_does_not_stop_during_short_pause(self):
        chunk = repeated_sample(1200, 1600)
        quiet = repeated_sample(0, 1600)
        chunks = [chunk, chunk, quiet, quiet, chunk, chunk, quiet, quiet, quiet, quiet, quiet]
        ratios = [1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0]
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = record_to_wav(
                chunks,
                sample_rate=16000,
                silence_seconds=0.3,
                end_silence_seconds=0.3,
                max_record_seconds=2.0,
                vad_detector=SequenceVad(ratios),
                vad_enabled=True,
                hangover_seconds=0.2,
                output_path=Path(tmp_dir) / "input.wav",
            )
        self.assertEqual(result.stopped_by, "silence")
        self.assertGreaterEqual(result.chunks_recorded, 9)

    def test_recorder_vad_stops_on_non_voice_noise(self):
        noise = repeated_sample(650, 1600)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = record_to_wav(
                [noise] * 10,
                sample_rate=16000,
                silence_seconds=0.3,
                end_silence_seconds=0.3,
                max_record_seconds=2.0,
                silence_threshold=750,
                vad_detector=SequenceVad([0.0] * 10),
                vad_enabled=True,
                hangover_seconds=0,
                output_path=Path(tmp_dir) / "input.wav",
            )
        self.assertEqual(result.stopped_by, "silence")
        self.assertEqual(result.chunks_recorded, 3)

    def test_recorder_vad_low_energy_wins_over_false_high_vad_after_speech(self):
        speech = repeated_sample(1400, 1600)
        quiet = repeated_sample(100, 1600)
        chunks = [speech, speech] + [quiet] * 10
        ratios = [1.0, 1.0] + [1.0] * 10
        logger = logging.getLogger("tests.recorder.false_high_vad")
        with tempfile.TemporaryDirectory() as tmp_dir, self.assertLogs(logger, level="INFO") as logs:
            result = record_to_wav(
                chunks,
                sample_rate=16000,
                silence_seconds=0.3,
                end_silence_seconds=0.3,
                max_record_seconds=2.0,
                silence_threshold=750,
                vad_detector=SequenceVad(ratios),
                vad_enabled=True,
                hangover_seconds=0.2,
                logger=logger,
                output_path=Path(tmp_dir) / "input.wav",
            )
        self.assertEqual(result.stopped_by, "silence")
        self.assertEqual(result.chunks_recorded, 7)
        self.assertIn("low_energy_high_vad_chunks=5", "\n".join(logs.output))

    def test_recorder_vad_requires_energy_and_vad_to_extend_recording(self):
        speech = repeated_sample(1400, 1600)
        quiet = repeated_sample(100, 1600)
        chunks = [speech, speech, quiet, quiet, quiet, quiet]
        ratios = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = record_to_wav(
                chunks,
                sample_rate=16000,
                silence_seconds=0.2,
                end_silence_seconds=0.2,
                max_record_seconds=2.0,
                silence_threshold=750,
                vad_detector=SequenceVad(ratios),
                vad_enabled=True,
                hangover_seconds=0,
                output_path=Path(tmp_dir) / "input.wav",
            )
        self.assertEqual(result.stopped_by, "silence")
        self.assertEqual(result.chunks_recorded, 4)

    def test_recorder_vad_does_not_call_high_rms_noise_silence(self):
        noise = repeated_sample(1800, 1600)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = record_to_wav(
                [noise] * 6,
                sample_rate=16000,
                silence_seconds=0.2,
                end_silence_seconds=0.2,
                max_record_seconds=0.4,
                vad_detector=SequenceVad([0.0] * 6),
                vad_enabled=True,
                hangover_seconds=0,
                output_path=Path(tmp_dir) / "input.wav",
            )
        self.assertEqual(result.stopped_by, "max_duration")

    def test_recorder_without_vad_preserves_rms_endpointing(self):
        speech = repeated_sample(1200, 1600)
        silence = repeated_sample(0, 1600)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = record_to_wav(
                [speech, silence, silence],
                sample_rate=16000,
                silence_seconds=0.2,
                max_record_seconds=2.0,
                output_path=Path(tmp_dir) / "input.wav",
            )
        self.assertEqual(result.stopped_by, "silence")


if __name__ == "__main__":
    unittest.main()

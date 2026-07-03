import struct
import tempfile
import unittest
import wave
from pathlib import Path

from src.recorder import record_to_wav


def repeated_sample(sample: int, frames: int) -> bytes:
    return struct.pack(f"<{frames}h", *([sample] * frames))


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

    def test_invalid_pcm_chunk_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                record_to_wav(
                    [b"\x00"],
                    silence_seconds=0.1,
                    max_record_seconds=1.0,
                    output_path=Path(tmp_dir) / "input.wav",
                )


if __name__ == "__main__":
    unittest.main()

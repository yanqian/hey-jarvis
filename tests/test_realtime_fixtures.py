from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path

from src.realtime.fixtures import FixtureError, load_manifest, record_fixture, trim_replay_fixture


class FakeSource:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = list(chunks)
        self.last_overflowed = False
        self.closed = False

    def read_chunk(self) -> bytes:
        chunk = self.chunks.pop(0)
        self.last_overflowed = not self.last_overflowed
        return chunk

    def close(self) -> None:
        self.closed = True


class RealtimeFixtureTests(unittest.TestCase):
    def test_records_private_wav_and_metadata_without_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = FakeSource([b"\x01\x00" * 8000, b"\x02\x00" * 8000])
            result = record_fixture(source, name="wake", duration_seconds=1.0, root=root)

            self.assertTrue(source.closed)
            self.assertEqual(result.duration_seconds, 1.0)
            self.assertEqual(result.overflow_chunks, 1)
            with wave.open(str(root / "wake.wav"), "rb") as audio:
                self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (1, 2, 16000))
                self.assertEqual(audio.getnframes(), 16000)
            manifest_text = (root / "manifest.json").read_text()
            self.assertNotIn("transcript", manifest_text.lower())
            self.assertEqual(load_manifest(root)["wake"].sha256, result.sha256)
            self.assertEqual(json.loads(manifest_text)["privacy"], "local-only; contains voice recordings; never commit")

    def test_rejects_unknown_name_and_still_closes_source_on_capture_error(self):
        source = FakeSource([])
        with self.assertRaisesRegex(FixtureError, "fixture name"):
            record_fixture(source, name="secret", duration_seconds=1.0)
        self.assertFalse(source.closed)

        source = FakeSource([b"odd"])
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(FixtureError, "int16"):
            record_fixture(source, name="wake", duration_seconds=1.0, root=Path(tmp))
        self.assertTrue(source.closed)

    def test_trim_creates_replay_derivative_without_changing_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = FakeSource([b"\x01\x00" * 16000])
            original = record_fixture(source, name="turn-1", duration_seconds=1.0, root=root)
            replay = trim_replay_fixture(name="turn-1", start_seconds=0.25, end_seconds=0.75, root=root)
            self.assertEqual(replay.duration_seconds, 0.5)
            self.assertNotEqual(replay.sha256, original.sha256)
            with wave.open(str(root / "replay" / "turn-1.wav"), "rb") as audio:
                self.assertEqual(audio.getnframes(), 8000)
            with wave.open(str(root / "turn-1.wav"), "rb") as audio:
                self.assertEqual(audio.getnframes(), 16000)


if __name__ == "__main__":
    unittest.main()

import struct
import unittest

from src.silence import is_silence, rms_level


def pcm_samples(*samples: int) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


class SilenceTests(unittest.TestCase):
    def test_zero_and_low_rms_chunks_are_silence(self):
        self.assertTrue(is_silence(pcm_samples(0, 0, 0, 0)))
        self.assertTrue(is_silence(pcm_samples(100, -100, 100, -100), threshold=150))

    def test_loud_rms_chunk_is_not_silence(self):
        chunk = pcm_samples(1000, -1000, 1000, -1000)

        self.assertAlmostEqual(rms_level(chunk), 1000.0)
        self.assertFalse(is_silence(chunk, threshold=500))

    def test_empty_chunk_is_silence(self):
        self.assertEqual(rms_level(b""), 0.0)
        self.assertTrue(is_silence(b""))

    def test_invalid_pcm_shape_raises(self):
        with self.assertRaises(ValueError):
            is_silence(b"\x00")
        with self.assertRaises(ValueError):
            is_silence(pcm_samples(0), threshold=-1)


if __name__ == "__main__":
    unittest.main()

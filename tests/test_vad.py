import unittest
from unittest.mock import patch

from src.vad import DisabledVad, VadError, WebRtcVadDetector, build_vad_detector


class FakeWebRtcVad:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    def is_speech(self, frame, sample_rate):
        self.calls.append((frame, sample_rate))
        return self.decisions.pop(0)


class VadTests(unittest.TestCase):
    def test_disabled_vad_is_neutral(self):
        detector = DisabledVad()
        self.assertFalse(detector.is_enabled)
        self.assertIsNone(detector.analyze(b"\x00\x00" * 320, 16000))
        self.assertIsNone(detector.voiced_ratio(b"\x00\x00" * 320, 16000))

    def test_webrtc_vad_splits_80ms_chunk_into_20ms_frames(self):
        fake = FakeWebRtcVad([True, False, True, True])
        detector = WebRtcVadDetector(2, vad=fake)
        result = detector.analyze(b"\x01\x00" * 1280, 16000)
        self.assertEqual(result.total_frames, 4)
        self.assertEqual(result.voiced_frames, 3)
        self.assertEqual(result.voiced_ratio, 0.75)
        self.assertEqual([len(frame) for frame, _ in fake.calls], [640] * 4)

    def test_webrtc_vad_ignores_incomplete_trailing_frame(self):
        fake = FakeWebRtcVad([True])
        result = WebRtcVadDetector(vad=fake).analyze(b"\x01\x00" * 400, 16000)
        self.assertEqual(result.total_frames, 1)
        self.assertEqual(len(fake.calls), 1)

    def test_webrtc_vad_rejects_unsupported_sample_rate(self):
        with self.assertRaisesRegex(VadError, "sample rate"):
            WebRtcVadDetector(vad=FakeWebRtcVad([])).analyze(b"\x00\x00" * 320, 44100)

    def test_build_disabled_vad_has_no_optional_import(self):
        self.assertIsInstance(build_vad_detector("disabled"), DisabledVad)

    def test_import_failure_preserves_root_cause_and_install_guidance(self):
        with patch.dict("sys.modules", {"webrtcvad": None}):
            with self.assertRaisesRegex(VadError, "requirements-vad.txt") as raised:
                WebRtcVadDetector()
        self.assertIn("webrtcvad", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

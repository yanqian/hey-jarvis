import logging
import struct
import unittest

from src.audio_input import AudioInputError, MicrophoneStream


class FakeRawInputStream:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.closed = False
        self.read_calls = 0
        FakeRawInputStream.instances.append(self)

    def start(self):
        self.started = True

    def read(self, frames):
        self.read_calls += 1
        return struct.pack("<hh", 1, -1), False

    def close(self):
        self.closed = True


class FakeSoundDevice:
    RawInputStream = FakeRawInputStream


class BrokenSoundDevice:
    class RawInputStream:
        def __init__(self, **kwargs):
            raise RuntimeError("no input device")


class AudioInputTests(unittest.TestCase):
    def setUp(self):
        FakeRawInputStream.instances = []

    def test_microphone_stream_opens_reusable_16khz_mono_int16_stream(self):
        stream = MicrophoneStream(
            sample_rate=16000,
            block_frames=512,
            sounddevice_module=FakeSoundDevice,
        )

        stream.open()
        stream.open()
        chunk = stream.read_chunk()
        stream.close()

        self.assertEqual(len(FakeRawInputStream.instances), 1)
        raw_stream = FakeRawInputStream.instances[0]
        self.assertTrue(raw_stream.started)
        self.assertTrue(raw_stream.closed)
        self.assertEqual(raw_stream.kwargs["samplerate"], 16000)
        self.assertEqual(raw_stream.kwargs["channels"], 1)
        self.assertEqual(raw_stream.kwargs["dtype"], "int16")
        self.assertEqual(raw_stream.kwargs["blocksize"], 512)
        self.assertEqual(chunk, struct.pack("<hh", 1, -1))

    def test_open_failure_logs_recovery_guidance(self):
        logger = logging.getLogger("tests.audio_input")
        stream = MicrophoneStream(sounddevice_module=BrokenSoundDevice, logger=logger)

        with self.assertLogs(logger, level="ERROR") as logs:
            with self.assertRaises(AudioInputError):
                stream.open()

        self.assertIn("grant macOS microphone permission", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()

import logging
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src.wake_word import (
    OPENWAKEWORD_INFERENCE_FRAMEWORK,
    OPENWAKEWORD_MODEL_KEY,
    OPENWAKEWORD_MODEL_NAME,
    WakeWordDetector,
    WakeWordError,
    prepare_wake_word_models,
)


def pcm_samples(*samples: int) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


class FakeWakeWordModel:
    def __init__(self, scores):
        self.scores = list(scores)
        self.frames = []

    def predict(self, frame):
        self.frames.append(frame)
        return self.scores.pop(0)


class WakeWordDetectorTests(unittest.TestCase):
    def test_detect_returns_false_below_threshold_and_true_at_threshold(self):
        model = FakeWakeWordModel(
            [
                {"hey jarvis": 0.79},
                {"hey jarvis": 0.8},
            ]
        )
        detector = WakeWordDetector(0.8, model=model)

        self.assertFalse(detector.detect(pcm_samples(1, 2, 3)))
        self.assertTrue(detector.detect(pcm_samples(4, 5, 6)))
        self.assertEqual(len(model.frames), 2)

    def test_detect_accepts_openwakeword_underscore_score_key(self):
        detector = WakeWordDetector(0.6, model=FakeWakeWordModel([{"hey_jarvis": 0.7}]))

        self.assertTrue(detector.detect(pcm_samples(10, -10)))

    def test_default_loader_uses_builtin_hey_jarvis_model_name(self):
        constructed_with = []

        class FakeOpenWakeWordModel:
            def __init__(self, wakeword_models, inference_framework):
                constructed_with.append((wakeword_models, inference_framework))

            def predict(self, frame):
                return {"hey jarvis": 0.9}

        openwakeword_module = types.ModuleType("openwakeword")
        model_module = types.ModuleType("openwakeword.model")
        model_module.Model = FakeOpenWakeWordModel

        with patch.dict(
            sys.modules,
            {
                "openwakeword": openwakeword_module,
                "openwakeword.model": model_module,
            },
        ):
            detector = WakeWordDetector(0.8)
            self.assertTrue(detector.detect(pcm_samples(0, 0, 0)))

        self.assertEqual(constructed_with, [([OPENWAKEWORD_MODEL_NAME], OPENWAKEWORD_INFERENCE_FRAMEWORK)])

    def test_prepare_wake_word_models_downloads_only_onnx_assets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_dir = Path(tmp_dir) / "models"
            openwakeword_module = types.ModuleType("openwakeword")
            openwakeword_module.FEATURE_MODELS = {
                "melspectrogram": {
                    "model_path": str(model_dir / "melspectrogram.tflite"),
                    "download_url": "https://example.test/melspectrogram.tflite",
                },
                "embedding": {
                    "model_path": str(model_dir / "embedding_model.tflite"),
                    "download_url": "https://example.test/embedding_model.tflite",
                },
            }
            openwakeword_module.MODELS = {
                OPENWAKEWORD_MODEL_KEY: {
                    "model_path": str(model_dir / "hey_jarvis_v0.1.tflite"),
                    "download_url": "https://example.test/hey_jarvis_v0.1.tflite",
                }
            }
            downloaded_urls = []

            def fake_urlretrieve(url, filename):
                downloaded_urls.append(url)
                Path(filename).write_bytes(b"onnx")

            with patch.dict(sys.modules, {"openwakeword": openwakeword_module}):
                with patch("src.wake_word.urlretrieve", side_effect=fake_urlretrieve):
                    prepared = prepare_wake_word_models()

            self.assertEqual(set(prepared), {"melspectrogram", "embedding", OPENWAKEWORD_MODEL_KEY})
            self.assertTrue(all(str(path).endswith(".onnx") for path in prepared.values()))
            self.assertTrue(all(path.is_file() for path in prepared.values()))
            self.assertTrue(all(url.endswith(".onnx") for url in downloaded_urls))
            self.assertFalse(any(url.endswith(".tflite") for url in downloaded_urls))

    def test_load_failure_logs_recovery_guidance(self):
        logger = logging.getLogger("tests.wake_word.load")

        def broken_factory():
            raise RuntimeError("model files unavailable")

        detector = WakeWordDetector(0.8, model_factory=broken_factory, logger=logger)

        with self.assertLogs(logger, level="ERROR") as logs:
            with self.assertRaises(WakeWordError):
                detector.detect(pcm_samples(0, 0))

        self.assertIn("prepare-wake-word", "\n".join(logs.output))

    def test_inference_failure_logs_clear_error(self):
        logger = logging.getLogger("tests.wake_word.inference")

        class BrokenModel:
            def predict(self, frame):
                raise RuntimeError("bad frame")

        detector = WakeWordDetector(0.8, model=BrokenModel(), logger=logger)

        with self.assertLogs(logger, level="ERROR") as logs:
            with self.assertRaises(WakeWordError):
                detector.detect(pcm_samples(0, 0))

        self.assertIn("Wake-word inference failed", "\n".join(logs.output))

    def test_invalid_pcm_chunk_is_rejected(self):
        detector = WakeWordDetector(0.8, model=FakeWakeWordModel([{"hey jarvis": 1.0}]))

        with self.assertRaises(ValueError):
            detector.detect(b"\x00")


if __name__ == "__main__":
    unittest.main()

import logging
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src.wake_word import (
    OPENWAKEWORD_FRAME_SAMPLES,
    OPENWAKEWORD_INFERENCE_FRAMEWORK,
    OPENWAKEWORD_MODEL_KEY,
    OPENWAKEWORD_MODEL_NAME,
    MACOS_ARM64_ONNX_ERROR,
    WakeWordDetector,
    WakeWordError,
    pad_pcm_chunk,
    pcm_rms_and_peak,
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
                {"alexa": 0.49},
                {"alexa": 0.5},
            ]
        )
        detector = WakeWordDetector(0.5, model=model)

        self.assertFalse(detector.detect(pcm_samples(1, 2, 3)))
        self.assertTrue(detector.detect(pcm_samples(4, 5, 6)))
        self.assertEqual(len(model.frames), 2)

    def test_score_returns_raw_alexa_score(self):
        detector = WakeWordDetector(0.5, model=FakeWakeWordModel([{"alexa": 0.42}]))

        self.assertEqual(detector.score(pcm_samples(1, 2, 3)), 0.42)

    def test_pcm_rms_and_peak_reports_int16_levels(self):
        rms, peak = pcm_rms_and_peak(pcm_samples(3, -4))

        self.assertAlmostEqual(rms, 3.5355, places=3)
        self.assertEqual(peak, 4)

    def test_detect_accepts_alexa_model_score_key(self):
        detector = WakeWordDetector(0.6, model=FakeWakeWordModel([{OPENWAKEWORD_MODEL_KEY: 0.7}]))

        self.assertTrue(detector.detect(pcm_samples(10, -10)))

    def test_preload_warms_model_with_openwakeword_prediction_frame(self):
        model = FakeWakeWordModel([{"alexa": 0.0}])
        detector = WakeWordDetector(0.5, model=model)

        detector.preload()

        self.assertEqual(len(model.frames), 1)
        self.assertEqual(len(model.frames[0]), OPENWAKEWORD_FRAME_SAMPLES)
        self.assertEqual(detector.frame_length, OPENWAKEWORD_FRAME_SAMPLES)

    def test_score_returns_safe_fallback_for_single_prediction_key(self):
        detector = WakeWordDetector(0.5, model=FakeWakeWordModel([{"alexa_v0.1": 0.61}]))

        self.assertEqual(detector.score(pcm_samples(1, 2, 3)), 0.61)

    def test_default_loader_uses_builtin_alexa_model_name_and_tflite(self):
        constructed_with = []

        class FakeOpenWakeWordModel:
            def __init__(self, wakeword_models, inference_framework):
                constructed_with.append((wakeword_models, inference_framework))

            def predict(self, frame):
                return {"alexa": 0.9}

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
            detector = WakeWordDetector(0.5)
            self.assertTrue(detector.detect(pcm_samples(0, 0, 0)))

        self.assertEqual(constructed_with, [([OPENWAKEWORD_MODEL_NAME], OPENWAKEWORD_INFERENCE_FRAMEWORK)])
        self.assertEqual(OPENWAKEWORD_INFERENCE_FRAMEWORK, "tflite")

    def test_loader_accepts_explicit_onnx_on_non_macos_arm64(self):
        constructed_with = []

        class FakeOpenWakeWordModel:
            def __init__(self, wakeword_models, inference_framework):
                constructed_with.append((wakeword_models, inference_framework))

            def predict(self, frame):
                return {"alexa": 0.9}

        openwakeword_module = types.ModuleType("openwakeword")
        model_module = types.ModuleType("openwakeword.model")
        model_module.Model = FakeOpenWakeWordModel

        with patch("src.wake_word.platform.system", return_value="Linux"):
            with patch("src.wake_word.platform.machine", return_value="x86_64"):
                with patch.dict(
                    sys.modules,
                    {
                        "openwakeword": openwakeword_module,
                        "openwakeword.model": model_module,
                    },
                ):
                    detector = WakeWordDetector(0.5, inference_framework="onnx")
                    self.assertTrue(detector.detect(pcm_samples(0, 0, 0)))

        self.assertEqual(constructed_with, [([OPENWAKEWORD_MODEL_NAME], "onnx")])

    def test_onnx_is_rejected_on_macos_arm64(self):
        with patch("src.wake_word.platform.system", return_value="Darwin"):
            with patch("src.wake_word.platform.machine", return_value="arm64"):
                with self.assertRaises(WakeWordError) as caught:
                    WakeWordDetector(0.5, inference_framework="onnx")

        self.assertIn(MACOS_ARM64_ONNX_ERROR, str(caught.exception))

    def test_prepare_wake_word_models_downloads_tflite_assets_by_default(self):
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
                    "model_path": str(model_dir / "alexa_v0.1.tflite"),
                    "download_url": "https://example.test/alexa_v0.1.tflite",
                }
            }
            downloaded_urls = []

            def fake_urlretrieve(url, filename):
                downloaded_urls.append(url)
                Path(filename).write_bytes(b"tflite")

            with patch.dict(sys.modules, {"openwakeword": openwakeword_module}):
                with patch("src.wake_word.urlretrieve", side_effect=fake_urlretrieve):
                    prepared = prepare_wake_word_models()

            self.assertEqual(set(prepared), {"melspectrogram", "embedding", OPENWAKEWORD_MODEL_KEY})
            self.assertTrue(all(str(path).endswith(".tflite") for path in prepared.values()))
            self.assertTrue(all(path.is_file() for path in prepared.values()))
            self.assertTrue(all(url.endswith(".tflite") for url in downloaded_urls))
            self.assertFalse(any(url.endswith(".onnx") for url in downloaded_urls))

    def test_prepare_wake_word_models_can_download_explicit_onnx_assets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_dir = Path(tmp_dir) / "models"
            openwakeword_module = types.ModuleType("openwakeword")
            openwakeword_module.FEATURE_MODELS = {
                "melspectrogram": {
                    "model_path": str(model_dir / "melspectrogram.tflite"),
                    "download_url": "https://example.test/melspectrogram.tflite",
                },
            }
            openwakeword_module.MODELS = {
                OPENWAKEWORD_MODEL_KEY: {
                    "model_path": str(model_dir / "alexa_v0.1.tflite"),
                    "download_url": "https://example.test/alexa_v0.1.tflite",
                }
            }
            downloaded_urls = []

            def fake_urlretrieve(url, filename):
                downloaded_urls.append(url)
                Path(filename).write_bytes(b"onnx")

            with patch("src.wake_word.platform.system", return_value="Linux"):
                with patch("src.wake_word.platform.machine", return_value="x86_64"):
                    with patch.dict(sys.modules, {"openwakeword": openwakeword_module}):
                        with patch("src.wake_word.urlretrieve", side_effect=fake_urlretrieve):
                            prepared = prepare_wake_word_models(inference_framework="onnx")

            self.assertTrue(all(str(path).endswith(".onnx") for path in prepared.values()))
            self.assertTrue(all(url.endswith(".onnx") for url in downloaded_urls))

    def test_load_failure_logs_recovery_guidance(self):
        logger = logging.getLogger("tests.wake_word.load")

        def broken_factory():
            raise RuntimeError("model files unavailable")

        detector = WakeWordDetector(0.5, model_factory=broken_factory, logger=logger)

        with self.assertLogs(logger, level="ERROR") as logs:
            with self.assertRaises(WakeWordError):
                detector.detect(pcm_samples(0, 0))

        self.assertIn("prepare-wake-word", "\n".join(logs.output))

    def test_inference_failure_logs_clear_error(self):
        logger = logging.getLogger("tests.wake_word.inference")

        class BrokenModel:
            def predict(self, frame):
                raise RuntimeError("bad frame")

        detector = WakeWordDetector(0.5, model=BrokenModel(), logger=logger)

        with self.assertLogs(logger, level="ERROR") as logs:
            with self.assertRaises(WakeWordError):
                detector.detect(pcm_samples(0, 0))

        self.assertIn("Wake-word inference failed", "\n".join(logs.output))

    def test_invalid_pcm_chunk_is_rejected(self):
        detector = WakeWordDetector(0.5, model=FakeWakeWordModel([{"alexa": 1.0}]))

        with self.assertRaises(ValueError):
            detector.detect(b"\x00")

    def test_final_short_chunk_padding_is_deterministic_for_file_replay(self):
        padded = pad_pcm_chunk(pcm_samples(777), frame_length=OPENWAKEWORD_FRAME_SAMPLES)

        self.assertEqual(len(padded), OPENWAKEWORD_FRAME_SAMPLES * 2)
        self.assertEqual(padded[:2], pcm_samples(777))
        self.assertEqual(padded[2:], b"\x00" * ((OPENWAKEWORD_FRAME_SAMPLES - 1) * 2))


if __name__ == "__main__":
    unittest.main()

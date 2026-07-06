import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts import debug_oww_file


class DebugOpenWakeWordFileScriptTests(unittest.TestCase):
    def test_script_defaults_to_hey_jarvis_model(self):
        self.assertEqual(debug_oww_file.DEFAULT_WAKE_MODEL, "hey_jarvis")

    def test_script_prints_model_framework_loaded_keys_and_max_scores(self):
        class FakeAudio:
            shape = (debug_oww_file.CHUNK_SAMPLES,)
            nbytes = debug_oww_file.CHUNK_SAMPLES * 2
            dtype = "int16"

            def __getitem__(self, item):
                return self

        class FakeModel:
            def __init__(self, wakeword_models, inference_framework):
                self.wakeword_models = wakeword_models
                self.inference_framework = inference_framework
                self.models = {"alexa": object()}

            def predict(self, chunk):
                return {"alexa": 0.75, "other": 0.25}

        model_module = types.ModuleType("openwakeword.model")
        model_module.Model = FakeModel
        openwakeword_module = types.ModuleType("openwakeword")

        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "wake.wav"
            wav_path.write_bytes(b"fake-wav")

            output = StringIO()
            with patch.dict(
                sys.modules,
                {"openwakeword": openwakeword_module, "openwakeword.model": model_module},
            ):
                with patch("scripts.debug_oww_file.load_wav", return_value=(FakeAudio(), 16000, 1, "int16")):
                    with patch("scripts.debug_oww_file.ensure_mono", side_effect=lambda audio: audio):
                        with patch("scripts.debug_oww_file.ensure_rate", side_effect=lambda audio, *_: audio):
                            with patch("scripts.debug_oww_file.ensure_int16", side_effect=lambda audio: audio):
                                with patch("scripts.debug_oww_file.pad_to_chunk_size", side_effect=lambda audio, *_: audio):
                                    with redirect_stdout(output):
                                        result = debug_oww_file.main(
                                            ["debug_oww_file.py", str(wav_path), "alexa", "tflite"]
                                        )

        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("requested_model = 'alexa'", text)
        self.assertIn("selected_inference_framework = 'tflite'", text)
        self.assertIn("loaded_models = ['alexa']", text)
        self.assertIn("max_score_per_key = {'alexa': 0.750000000, 'other': 0.250000000}", text)


if __name__ == "__main__":
    unittest.main()

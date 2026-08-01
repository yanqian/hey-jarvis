"""Runtime-only openWakeWord package surface for the Hey Jarvis TFLite build.

The upstream package initializer eagerly imports ONNX VAD and SciPy/sklearn
verifier-training modules. Hey Jarvis uses neither in the packaged product.
Keeping metadata here lets the unmodified upstream model and utility modules
load exactly the three audited TFLite assets without shipping those optional
training and ONNX stacks.
"""

from __future__ import annotations

import os


_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "models")

FEATURE_MODELS = {
    "embedding": {
        "model_path": os.path.join(_MODELS_DIR, "embedding_model.tflite"),
        "download_url": "",
    },
    "melspectrogram": {
        "model_path": os.path.join(_MODELS_DIR, "melspectrogram.tflite"),
        "download_url": "",
    },
}
MODELS = {
    "hey_jarvis": {
        "model_path": os.path.join(_MODELS_DIR, "hey_jarvis_v0.1.tflite"),
        "download_url": "",
    }
}
VAD_MODELS = {}
model_class_mappings = {}


def get_pretrained_model_paths(inference_framework: str = "tflite") -> list[str]:
    if inference_framework != "tflite":
        raise ValueError("the packaged Hey Jarvis runtime supports only tflite")
    return [MODELS["hey_jarvis"]["model_path"]]


def __getattr__(name: str):
    if name == "Model":
        from openwakeword.model import Model

        return Model
    raise AttributeError(name)

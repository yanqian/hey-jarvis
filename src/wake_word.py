"""Wake-word detection boundary for openWakeWord."""

from __future__ import annotations

import logging
from pathlib import Path
import struct
from typing import Any, Callable, Mapping, Protocol
from urllib.request import urlretrieve


OPENWAKEWORD_MODEL_NAME = "hey jarvis"
OPENWAKEWORD_MODEL_KEY = "hey_jarvis"
OPENWAKEWORD_INFERENCE_FRAMEWORK = "onnx"
OPENWAKEWORD_FRAME_SAMPLES = 1280
OPENWAKEWORD_SCORE_KEYS = (OPENWAKEWORD_MODEL_NAME, "hey_jarvis")
PREPARE_WAKE_WORD_COMMAND = "python -m src.main --prepare-wake-word"
WAKEWORD_RECOVERY_GUIDANCE = (
    "Install requirements.txt, then run "
    f"`{PREPARE_WAKE_WORD_COMMAND}` before real wake-word detection."
)


class WakeWordError(RuntimeError):
    """Raised when the wake-word model cannot load or run inference."""


class WakeWordModel(Protocol):
    def predict(self, frame: Any) -> Mapping[str, float]:
        """Return wake-word prediction scores for one audio frame."""


class WakeWordDetector:
    """Detect the built-in Hey Jarvis wake word from int16 PCM chunks."""

    def __init__(
        self,
        threshold: float,
        *,
        model: WakeWordModel | None = None,
        model_factory: Callable[[], WakeWordModel] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")

        self.threshold = threshold
        self._model = model
        self._model_factory = model_factory or _load_openwakeword_model
        self._logger = logger or logging.getLogger(__name__)

    def detect(self, pcm_chunk: bytes) -> bool:
        """Return true when the Hey Jarvis score crosses the configured threshold."""

        if len(pcm_chunk) % 2 != 0:
            raise ValueError("PCM chunks must contain complete int16 samples")

        model = self._get_model()
        frame = _pcm_bytes_to_model_frame(pcm_chunk)

        try:
            predictions = model.predict(frame)
            score = _hey_jarvis_score(predictions)
        except Exception as exc:
            self._logger.error("Wake-word inference failed for the Hey Jarvis model: %s", exc)
            raise WakeWordError(f"Wake-word inference failed: {exc}") from exc

        return score >= self.threshold

    def preload(self) -> None:
        """Load and warm the wake-word model before microphone capture starts."""

        model = self._get_model()
        try:
            model.predict(_silent_model_frame())
        except Exception as exc:
            self._logger.error("Wake-word model warmup failed for the Hey Jarvis model: %s", exc)
            raise WakeWordError(f"Wake-word model warmup failed: {exc}") from exc

    def _get_model(self) -> WakeWordModel:
        if self._model is not None:
            return self._model

        try:
            model = self._model_factory()
        except Exception as exc:
            self._logger.error("Unable to load the openWakeWord Hey Jarvis model. %s", WAKEWORD_RECOVERY_GUIDANCE)
            raise WakeWordError(f"Unable to load wake-word model: {exc}") from exc

        if model is None:
            self._logger.error("Unable to load the openWakeWord Hey Jarvis model. Model factory returned None.")
            raise WakeWordError("Unable to load wake-word model: model factory returned None")

        self._model = model
        return model


def _load_openwakeword_model() -> WakeWordModel:
    from openwakeword.model import Model

    return Model(
        wakeword_models=[OPENWAKEWORD_MODEL_NAME],
        inference_framework=OPENWAKEWORD_INFERENCE_FRAMEWORK,
    )


def required_wake_word_model_paths() -> Mapping[str, Path]:
    """Return the ONNX model files required by the built-in Hey Jarvis path."""

    import openwakeword

    paths: dict[str, Path] = {}
    for name, metadata in openwakeword.FEATURE_MODELS.items():
        paths[name] = _onnx_path(metadata["model_path"])
    paths[OPENWAKEWORD_MODEL_KEY] = _onnx_path(openwakeword.MODELS[OPENWAKEWORD_MODEL_KEY]["model_path"])
    return paths


def missing_wake_word_model_paths() -> Mapping[str, Path]:
    """Return required wake-word ONNX model paths that are not present."""

    return {
        name: path
        for name, path in required_wake_word_model_paths().items()
        if not path.is_file()
    }


def prepare_wake_word_models(logger: logging.Logger | None = None) -> Mapping[str, Path]:
    """Download the ONNX model assets required for the Hey Jarvis wake word."""

    import openwakeword

    log = logger or logging.getLogger(__name__)
    downloads: dict[str, tuple[str, Path]] = {}
    for name, metadata in openwakeword.FEATURE_MODELS.items():
        downloads[name] = (_onnx_url(metadata["download_url"]), _onnx_path(metadata["model_path"]))
    downloads[OPENWAKEWORD_MODEL_KEY] = (
        _onnx_url(openwakeword.MODELS[OPENWAKEWORD_MODEL_KEY]["download_url"]),
        _onnx_path(openwakeword.MODELS[OPENWAKEWORD_MODEL_KEY]["model_path"]),
    )

    prepared: dict[str, Path] = {}
    for name, (url, path) in downloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            log.info("Wake-word ONNX model already present: %s", path)
        else:
            log.info("Downloading wake-word ONNX model %s", path.name)
            urlretrieve(url, path)
        prepared[name] = path
    return prepared


def _onnx_path(path: str | Path) -> Path:
    return Path(str(path).replace(".tflite", ".onnx"))


def _onnx_url(url: str) -> str:
    return url.replace(".tflite", ".onnx")


def _pcm_bytes_to_model_frame(pcm_chunk: bytes) -> Any:
    try:
        import numpy as np
    except ImportError:
        return tuple(sample for (sample,) in struct.iter_unpack("<h", pcm_chunk))

    return np.frombuffer(pcm_chunk, dtype=np.int16)


def _silent_model_frame() -> Any:
    pcm_chunk = b"\x00\x00" * OPENWAKEWORD_FRAME_SAMPLES
    return _pcm_bytes_to_model_frame(pcm_chunk)


def _hey_jarvis_score(predictions: Mapping[str, float]) -> float:
    for key in OPENWAKEWORD_SCORE_KEYS:
        if key in predictions:
            return float(predictions[key])

    if len(predictions) == 1:
        return float(next(iter(predictions.values())))

    keys = ", ".join(sorted(str(key) for key in predictions))
    raise KeyError(f"Hey Jarvis score missing from wake-word predictions: {keys}")

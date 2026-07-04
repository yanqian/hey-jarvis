"""Wake-word detection boundary for openWakeWord."""

from __future__ import annotations

import logging
import math
from pathlib import Path
import struct
from typing import Any, Callable, Mapping, Protocol
from urllib.request import urlretrieve


OPENWAKEWORD_MODEL_NAME = "alexa"
OPENWAKEWORD_MODEL_KEY = "alexa"
OPENWAKEWORD_INFERENCE_FRAMEWORK = "onnx"
OPENWAKEWORD_FRAME_SAMPLES = 1280
OPENWAKEWORD_SAMPLE_RATE = 16000
OPENWAKEWORD_SCORE_KEYS = (OPENWAKEWORD_MODEL_KEY, OPENWAKEWORD_MODEL_NAME)
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
    """Detect the built-in Alexa wake word from int16 PCM chunks."""

    frame_length = OPENWAKEWORD_FRAME_SAMPLES
    sample_rate = OPENWAKEWORD_SAMPLE_RATE

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
        """Return true when the Alexa score crosses the configured threshold."""

        return self.score(pcm_chunk) >= self.threshold

    def score(self, pcm_chunk: bytes) -> float:
        """Return the Alexa score for one int16 PCM chunk."""

        if len(pcm_chunk) % 2 != 0:
            raise ValueError("PCM chunks must contain complete int16 samples")

        model = self._get_model()
        frame = _pcm_bytes_to_model_frame(pcm_chunk)

        try:
            predictions = model.predict(frame)
            score = _alexa_score(predictions)
        except Exception as exc:
            self._logger.error("Wake-word inference failed for the Alexa model: %s", exc)
            raise WakeWordError(f"Wake-word inference failed: {exc}") from exc

        return score

    def preload(self) -> None:
        """Load and warm the wake-word model before microphone capture starts."""

        model = self._get_model()
        try:
            model.predict(_silent_model_frame())
        except Exception as exc:
            self._logger.error("Wake-word model warmup failed for the Alexa model: %s", exc)
            raise WakeWordError(f"Wake-word model warmup failed: {exc}") from exc

    def close(self) -> None:
        """Keep a common detector cleanup hook for callers that support it."""

    def _get_model(self) -> WakeWordModel:
        if self._model is not None:
            return self._model

        try:
            model = self._model_factory()
        except Exception as exc:
            self._logger.error("Unable to load the openWakeWord Alexa model. %s", WAKEWORD_RECOVERY_GUIDANCE)
            raise WakeWordError(f"Unable to load wake-word model: {exc}") from exc

        if model is None:
            self._logger.error("Unable to load the openWakeWord Alexa model. Model factory returned None.")
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
    """Return the ONNX model files required by the built-in Alexa path."""

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
    """Download the ONNX model assets required for the Alexa wake word."""

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


def pad_pcm_chunk(pcm_chunk: bytes, *, frame_length: int = OPENWAKEWORD_FRAME_SAMPLES) -> bytes:
    """Pad a final short PCM chunk to a full openWakeWord frame with silence."""

    if len(pcm_chunk) % 2 != 0:
        raise ValueError("PCM chunks must contain complete int16 samples")
    frame_bytes = frame_length * 2
    if len(pcm_chunk) > frame_bytes:
        raise ValueError(f"PCM chunk has more than {frame_length} int16 samples")
    return pcm_chunk + (b"\x00" * (frame_bytes - len(pcm_chunk)))


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


def pcm_rms_and_peak(pcm_chunk: bytes) -> tuple[float, int]:
    """Return RMS and absolute peak for little-endian int16 PCM bytes."""

    if len(pcm_chunk) % 2 != 0:
        raise ValueError("PCM chunks must contain complete int16 samples")
    if not pcm_chunk:
        return 0.0, 0

    samples = [sample for (sample,) in struct.iter_unpack("<h", pcm_chunk)]
    peak = max(abs(sample) for sample in samples)
    mean_square = sum(sample * sample for sample in samples) / len(samples)
    return math.sqrt(mean_square), peak


def _silent_model_frame() -> Any:
    pcm_chunk = b"\x00\x00" * OPENWAKEWORD_FRAME_SAMPLES
    return _pcm_bytes_to_model_frame(pcm_chunk)


def _alexa_score(predictions: Mapping[str, float]) -> float:
    for key in OPENWAKEWORD_SCORE_KEYS:
        if key in predictions:
            return float(predictions[key])

    if len(predictions) == 1:
        return float(next(iter(predictions.values())))

    keys = ", ".join(sorted(str(key) for key in predictions))
    raise KeyError(f"Alexa score missing from wake-word predictions: {keys}")

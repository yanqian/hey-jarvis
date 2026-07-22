"""Wake-word detection boundary for openWakeWord."""

from __future__ import annotations

import logging
import math
import platform
from pathlib import Path
import struct
import sys
import types
from typing import Any, Callable, Mapping, Protocol
from urllib.request import urlretrieve


OPENWAKEWORD_BACKEND = "openwakeword"
OPENWAKEWORD_MODEL_NAME = "hey_jarvis"
OPENWAKEWORD_MODEL_KEY = "hey_jarvis"
OPENWAKEWORD_INFERENCE_FRAMEWORK = "tflite"
SUPPORTED_WAKE_BACKENDS = (OPENWAKEWORD_BACKEND,)
SUPPORTED_OPENWAKEWORD_INFERENCE_FRAMEWORKS = ("tflite", "onnx")
OPENWAKEWORD_FRAME_SAMPLES = 1280
OPENWAKEWORD_SAMPLE_RATE = 16000
PREPARE_WAKE_WORD_COMMAND = "python -m src.main --prepare-wake-word"
WAKEWORD_RECOVERY_GUIDANCE = (
    "Install requirements.txt, then run "
    f"`{PREPARE_WAKE_WORD_COMMAND}` before real wake-word detection."
)
MACOS_ARM64_ONNX_ERROR = (
    "WAKE_INFERENCE_FRAMEWORK=onnx is disabled on macOS ARM64 because openWakeWord ONNX "
    "has produced near-zero wake-word scores on Apple Silicon; use WAKE_INFERENCE_FRAMEWORK=tflite."
)


class WakeWordError(RuntimeError):
    """Raised when the wake-word model cannot load or run inference."""


class WakeWordModel(Protocol):
    def predict(self, frame: Any) -> Mapping[str, float]:
        """Return wake-word prediction scores for one audio frame."""


class WakeWordDetector:
    """Detect the configured built-in openWakeWord wake word from int16 PCM chunks."""

    frame_length = OPENWAKEWORD_FRAME_SAMPLES
    sample_rate = OPENWAKEWORD_SAMPLE_RATE

    def __init__(
        self,
        threshold: float,
        *,
        model_name: str = OPENWAKEWORD_MODEL_NAME,
        inference_framework: str = OPENWAKEWORD_INFERENCE_FRAMEWORK,
        vad_threshold: float | None = None,
        model: WakeWordModel | None = None,
        model_factory: Callable[[], WakeWordModel] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        if vad_threshold is not None and (vad_threshold < 0.0 or vad_threshold > 1.0):
            raise ValueError("vad_threshold must be between 0.0 and 1.0")

        self.threshold = threshold
        self.model_name = normalize_wake_model(model_name)
        self.model_key = wake_model_key(self.model_name)
        self.inference_framework = normalize_inference_framework(inference_framework)
        self.vad_threshold = vad_threshold
        reject_macos_arm64_onnx(self.inference_framework)
        self._model = model
        self._model_factory = model_factory or (
            lambda: _load_openwakeword_model(
                model_name=self.model_name,
                inference_framework=self.inference_framework,
                vad_threshold=self.vad_threshold,
            )
        )
        self._logger = logger or logging.getLogger(__name__)
        self._last_scores: dict[str, float] = {}

    def detect(self, pcm_chunk: bytes) -> bool:
        """Return true when the configured wake-word score crosses the threshold."""

        return self.score(pcm_chunk) >= self.threshold

    def reset(self) -> None:
        """Reset model streaming state before returning to fresh wake listening."""

        reset = getattr(self._model, "reset", None)
        if reset is not None:
            reset()
        self._last_scores = {}

    def score(self, pcm_chunk: bytes) -> float:
        """Return the configured wake-word score for one int16 PCM chunk."""

        if len(pcm_chunk) % 2 != 0:
            raise ValueError("PCM chunks must contain complete int16 samples")

        model = self._get_model()
        frame = _pcm_bytes_to_model_frame(pcm_chunk)

        try:
            predictions = model.predict(frame)
            self._last_scores = _float_scores(predictions)
            score = score_from_predictions(self._last_scores, model_key=self.model_key, model_name=self.model_name)
        except Exception as exc:
            self._logger.error("Wake-word inference failed for the %s model: %s", self.model_name, exc)
            raise WakeWordError(f"Wake-word inference failed: {exc}") from exc

        return score

    def score_details(self, pcm_chunk: bytes) -> Mapping[str, float]:
        """Return all model prediction scores for one int16 PCM chunk."""

        self.score(pcm_chunk)
        return dict(self._last_scores)

    def preload(self) -> None:
        """Load and warm the wake-word model before microphone capture starts."""

        model = self._get_model()
        try:
            model.predict(_silent_model_frame())
        except Exception as exc:
            self._logger.error("Wake-word model warmup failed for the %s model: %s", self.model_name, exc)
            raise WakeWordError(f"Wake-word model warmup failed: {exc}") from exc

    def close(self) -> None:
        """Keep a common detector cleanup hook for callers that support it."""

    def loaded_model_keys(self) -> tuple[str, ...]:
        """Return loaded openWakeWord model keys when the underlying model exposes them."""

        model = self._get_model()
        models = getattr(model, "models", None)
        if isinstance(models, Mapping):
            return tuple(str(key) for key in models.keys())
        return ()

    def _get_model(self) -> WakeWordModel:
        if self._model is not None:
            return self._model

        try:
            model = self._model_factory()
        except Exception as exc:
            self._logger.error(
                "Unable to load the openWakeWord %s model with %s inference. %s",
                self.model_name,
                self.inference_framework,
                WAKEWORD_RECOVERY_GUIDANCE,
            )
            raise WakeWordError(f"Unable to load wake-word model: {exc}") from exc

        if model is None:
            self._logger.error("Unable to load the openWakeWord %s model. Model factory returned None.", self.model_name)
            raise WakeWordError("Unable to load wake-word model: model factory returned None")

        self._model = model
        return model


def _load_openwakeword_model(
    *,
    model_name: str = OPENWAKEWORD_MODEL_NAME,
    inference_framework: str = OPENWAKEWORD_INFERENCE_FRAMEWORK,
    vad_threshold: float | None = None,
) -> WakeWordModel:
    inference_framework = normalize_inference_framework(inference_framework)
    reject_macos_arm64_onnx(inference_framework)
    if inference_framework == "tflite":
        _install_litert_compat_alias()

    from openwakeword.model import Model

    kwargs: dict[str, Any] = {
        "wakeword_models": [normalize_wake_model(model_name)],
        "inference_framework": inference_framework,
    }
    if vad_threshold is not None:
        kwargs["vad_threshold"] = vad_threshold
    try:
        return Model(**kwargs)
    except TypeError as exc:
        if vad_threshold is not None and "vad_threshold" in str(exc):
            raise WakeWordError(
                "WAKE_VAD_THRESHOLD is configured, but this openWakeWord version does not "
                "support the vad_threshold model argument; upgrade openwakeword or unset the setting"
            ) from exc
        raise


def required_wake_word_model_paths(
    *,
    model_name: str = OPENWAKEWORD_MODEL_NAME,
    inference_framework: str = OPENWAKEWORD_INFERENCE_FRAMEWORK,
) -> Mapping[str, Path]:
    """Return the model files required by the configured openWakeWord path."""

    import openwakeword

    model_key = wake_model_key(model_name)
    suffix = _framework_suffix(inference_framework)
    paths: dict[str, Path] = {}
    for name, metadata in openwakeword.FEATURE_MODELS.items():
        paths[name] = _model_asset_path(metadata["model_path"], suffix=suffix)
    paths[model_key] = _model_asset_path(openwakeword.MODELS[model_key]["model_path"], suffix=suffix)
    return paths


def missing_wake_word_model_paths(
    *,
    model_name: str = OPENWAKEWORD_MODEL_NAME,
    inference_framework: str = OPENWAKEWORD_INFERENCE_FRAMEWORK,
) -> Mapping[str, Path]:
    """Return required wake-word model paths that are not present."""

    return {
        name: path
        for name, path in required_wake_word_model_paths(
            model_name=model_name,
            inference_framework=inference_framework,
        ).items()
        if not path.is_file()
    }


def prepare_wake_word_models(
    *,
    model_name: str = OPENWAKEWORD_MODEL_NAME,
    inference_framework: str = OPENWAKEWORD_INFERENCE_FRAMEWORK,
    logger: logging.Logger | None = None,
) -> Mapping[str, Path]:
    """Download the model assets required for the configured wake word."""

    import openwakeword

    log = logger or logging.getLogger(__name__)
    model_key = wake_model_key(model_name)
    suffix = _framework_suffix(inference_framework)
    downloads: dict[str, tuple[str, Path]] = {}
    for name, metadata in openwakeword.FEATURE_MODELS.items():
        downloads[name] = (
            _model_asset_url(metadata["download_url"], suffix=suffix),
            _model_asset_path(metadata["model_path"], suffix=suffix),
        )
    downloads[model_key] = (
        _model_asset_url(openwakeword.MODELS[model_key]["download_url"], suffix=suffix),
        _model_asset_path(openwakeword.MODELS[model_key]["model_path"], suffix=suffix),
    )

    prepared: dict[str, Path] = {}
    for name, (url, path) in downloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            log.info("Wake-word %s model already present: %s", inference_framework, path)
        else:
            log.info("Downloading wake-word %s model %s", inference_framework, path.name)
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


def normalize_wake_backend(value: str) -> str:
    backend = value.strip().lower()
    if backend not in SUPPORTED_WAKE_BACKENDS:
        raise ValueError(f"unsupported wake backend {value!r}; supported values: {', '.join(SUPPORTED_WAKE_BACKENDS)}")
    return backend


def normalize_wake_model(value: str) -> str:
    model_name = value.strip().lower().replace(" ", "_")
    if not model_name:
        raise ValueError("wake model must not be empty")
    return model_name


def wake_model_key(model_name: str) -> str:
    return normalize_wake_model(model_name)


def normalize_inference_framework(value: str) -> str:
    framework = value.strip().lower()
    if framework not in SUPPORTED_OPENWAKEWORD_INFERENCE_FRAMEWORKS:
        supported = ", ".join(SUPPORTED_OPENWAKEWORD_INFERENCE_FRAMEWORKS)
        raise ValueError(f"unsupported wake inference framework {value!r}; supported values: {supported}")
    return framework


def reject_macos_arm64_onnx(inference_framework: str) -> None:
    if normalize_inference_framework(inference_framework) == "onnx" and is_macos_arm64():
        raise WakeWordError(MACOS_ARM64_ONNX_ERROR)


def is_macos_arm64() -> bool:
    return platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}


def _framework_suffix(inference_framework: str) -> str:
    return "." + normalize_inference_framework(inference_framework)


def _model_asset_path(path: str | Path, *, suffix: str) -> Path:
    return Path(str(path)).with_suffix(suffix)


def _model_asset_url(url: str, *, suffix: str) -> str:
    if url.endswith(".tflite") or url.endswith(".onnx"):
        return url.rsplit(".", 1)[0] + suffix
    return url


def _install_litert_compat_alias() -> None:
    if "tflite_runtime.interpreter" in sys.modules:
        return
    try:
        import tflite_runtime.interpreter  # noqa: F401

        return
    except ImportError:
        pass

    try:
        import ai_edge_litert.interpreter as interpreter
    except ImportError:
        return

    package = types.ModuleType("tflite_runtime")
    package.interpreter = interpreter
    sys.modules.setdefault("tflite_runtime", package)
    sys.modules.setdefault("tflite_runtime.interpreter", interpreter)


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


def _float_scores(predictions: Mapping[str, float]) -> dict[str, float]:
    return {str(key): float(value) for key, value in predictions.items()}


def score_from_predictions(
    predictions: Mapping[str, float],
    *,
    model_key: str = OPENWAKEWORD_MODEL_KEY,
    model_name: str = OPENWAKEWORD_MODEL_NAME,
) -> float:
    score_keys = (wake_model_key(model_key), normalize_wake_model(model_name), model_name)
    for key in score_keys:
        if key in predictions:
            return float(predictions[key])

    if len(predictions) == 1:
        return float(next(iter(predictions.values())))

    keys = ", ".join(sorted(str(key) for key in predictions))
    raise KeyError(f"{model_name} score missing from wake-word predictions: {keys}")

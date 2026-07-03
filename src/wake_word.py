"""Wake-word detection boundary for openWakeWord."""

from __future__ import annotations

import logging
import struct
from typing import Any, Callable, Mapping, Protocol


OPENWAKEWORD_MODEL_NAME = "hey jarvis"
OPENWAKEWORD_SCORE_KEYS = (OPENWAKEWORD_MODEL_NAME, "hey_jarvis")
WAKEWORD_RECOVERY_GUIDANCE = (
    "Install requirements.txt in a Python 3.11 or 3.12 environment before running "
    "real wake-word detection."
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

    return Model(wakeword_models=[OPENWAKEWORD_MODEL_NAME])


def _pcm_bytes_to_model_frame(pcm_chunk: bytes) -> Any:
    try:
        import numpy as np
    except ImportError:
        return tuple(sample for (sample,) in struct.iter_unpack("<h", pcm_chunk))

    return np.frombuffer(pcm_chunk, dtype=np.int16)


def _hey_jarvis_score(predictions: Mapping[str, float]) -> float:
    for key in OPENWAKEWORD_SCORE_KEYS:
        if key in predictions:
            return float(predictions[key])

    if len(predictions) == 1:
        return float(next(iter(predictions.values())))

    keys = ", ".join(sorted(str(key) for key in predictions))
    raise KeyError(f"Hey Jarvis score missing from wake-word predictions: {keys}")

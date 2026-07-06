#!/usr/bin/env python3
"""Minimal openWakeWord WAV-file probe for local debugging."""

from __future__ import annotations

import math
import sys
import types
import wave
from pathlib import Path


TARGET_RATE = 16000
CHUNK_SAMPLES = 1280
DEFAULT_WAKE_MODEL = "hey_jarvis"
DEFAULT_FRAMEWORK = "tflite"


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3, 4):
        print(
            "usage: python scripts/debug_oww_file.py path/to/audio.wav [wake_model] [tflite|onnx]",
            file=sys.stderr,
        )
        return 2

    wav_path = Path(argv[1])
    wake_model = argv[2] if len(argv) >= 3 else DEFAULT_WAKE_MODEL
    framework = argv[3] if len(argv) == 4 else DEFAULT_FRAMEWORK
    if framework not in {"tflite", "onnx"}:
        print("error: inference framework must be tflite or onnx", file=sys.stderr)
        return 2
    if not wav_path.is_file():
        print(f"error: file not found: {wav_path}", file=sys.stderr)
        return 1
    if framework == "tflite":
        install_litert_compat_alias()

    from openwakeword.model import Model

    audio, wav_rate, channels, dtype_name = load_wav(wav_path)
    audio = ensure_mono(audio)
    audio = ensure_rate(audio, wav_rate, TARGET_RATE)
    audio = ensure_int16(audio)
    audio = pad_to_chunk_size(audio, CHUNK_SAMPLES)

    model = Model(wakeword_models=[wake_model], inference_framework=framework)
    loaded_models = list(model.models.keys())

    max_score_per_key: dict[str, float] = {}
    prediction_keys: list[str] = []
    first_chunk_info: dict[str, object] | None = None
    for start in range(0, audio.shape[0], CHUNK_SAMPLES):
        chunk = audio[start : start + CHUNK_SAMPLES]
        if first_chunk_info is None:
            first_chunk_info = chunk_info(chunk)
        predictions = model.predict(chunk)
        for key, value in predictions.items():
            if key not in prediction_keys:
                prediction_keys.append(key)
            score = float(value)
            max_score_per_key[key] = max(max_score_per_key.get(key, 0.0), score)

    print(f"loaded_models = {loaded_models!r}")
    print(f"requested_model = {wake_model!r}")
    print(f"selected_inference_framework = {framework!r}")
    print(f"wav_rate = {wav_rate}")
    print(f"channels = {channels}")
    print(f"dtype = {dtype_name}")
    print(f"resampled_rate = {TARGET_RATE}")
    print(f"chunk_samples = {CHUNK_SAMPLES}")
    if first_chunk_info is not None:
        print(f"chunk_len_bytes = {first_chunk_info['len_bytes']}")
        print(f"chunk_len_samples = {first_chunk_info['len_samples']}")
        print(f"type(chunk) = {first_chunk_info['type']}")
        print(f"chunk.dtype = {first_chunk_info['dtype']}")
        print(f"chunk.shape = {first_chunk_info['shape']}")
    print(f"total_samples = {audio.shape[0]}")
    print(f"total_chunks = {audio.shape[0] // CHUNK_SAMPLES}")
    print(f"prediction_keys = {prediction_keys!r}")
    print(f"max_score_per_key = {format_scores(max_score_per_key)}")
    print(f"contains_hey_jarvis = {'hey_jarvis' in prediction_keys}")
    print(f"contains_hey_jarvis_spaced = {'hey jarvis' in prediction_keys}")
    return 0


def install_litert_compat_alias() -> None:
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


def load_wav(path: Path):
    np = _numpy()
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        wav_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    if sample_width == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.int16)
        data = (data - 128) << 8
        dtype_name = "uint8->int16"
    elif sample_width == 2:
        data = np.frombuffer(raw, dtype="<i2")
        dtype_name = "int16"
    elif sample_width == 4:
        data32 = np.frombuffer(raw, dtype="<i4")
        data = np.clip(data32 // 65536, -32768, 32767).astype(np.int16)
        dtype_name = "int32->int16"
    else:
        raise ValueError(f"unsupported WAV sample width: {sample_width} bytes")

    if channels > 1:
        data = data.reshape(-1, channels)

    return data, wav_rate, channels, dtype_name


def ensure_mono(audio):
    np = _numpy()
    if audio.ndim == 1:
        return audio
    return np.round(audio.astype(np.float32).mean(axis=1)).astype(np.int16)


def ensure_rate(audio, source_rate: int, target_rate: int):
    np = _numpy()
    if source_rate == target_rate:
        return audio

    divisor = math.gcd(source_rate, target_rate)
    up = target_rate // divisor
    down = source_rate // divisor
    resampled = _resample_poly()(audio.astype(np.float32), up, down)
    return np.clip(np.round(resampled), -32768, 32767).astype(np.int16)


def ensure_int16(audio):
    np = _numpy()
    if audio.dtype == np.int16:
        return audio
    return np.clip(np.round(audio), -32768, 32767).astype(np.int16)


def pad_to_chunk_size(audio, chunk_samples: int):
    np = _numpy()
    remainder = audio.shape[0] % chunk_samples
    if remainder == 0:
        return audio
    padding = chunk_samples - remainder
    return np.pad(audio, (0, padding), mode="constant").astype(np.int16)


def format_scores(scores: dict[str, float]) -> str:
    parts = [f"{key!r}: {value:.9f}" for key, value in scores.items()]
    return "{" + ", ".join(parts) + "}"


def chunk_info(chunk) -> dict[str, object]:
    return {
        "len_bytes": chunk.nbytes,
        "len_samples": chunk.shape[0],
        "type": f"{type(chunk).__module__}.{type(chunk).__qualname__}",
        "dtype": str(chunk.dtype),
        "shape": tuple(chunk.shape),
    }


def _numpy():
    import numpy as np

    return np


def _resample_poly():
    from scipy.signal import resample_poly

    return resample_poly


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

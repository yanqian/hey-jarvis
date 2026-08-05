"""Validation and promotion for the cached Mandarin Realtime farewell."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import tempfile
from pathlib import Path

from .realtime_ack_asset import inspect_wav, trim_bounded_silence


FAREWELL_PHRASE = "再见"
FAREWELL_PROMPT_VERSION = "mandarin-farewell-v1"
FAREWELL_GENERATION_MODEL = "gpt-4o-mini-tts"
MIN_FAREWELL_DURATION_MS = 150
MAX_FAREWELL_DURATION_MS = 3_000
CANDIDATE_LABEL = re.compile(r"^candidate-[0-9]{2}$")
CANONICAL_FAREWELL_ASSET = Path("assets/realtime_farewell_alloy_zh.wav")
CANONICAL_FAREWELL_MANIFEST = Path("assets/realtime_farewell_alloy_zh.json")


class RealtimeFarewellAssetError(ValueError):
    pass


def finalize_streaming_wav(data: bytes) -> bytes:
    """Replace streaming RIFF size sentinels with the received payload lengths."""

    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE" or data[36:40] != b"data":
        raise RealtimeFarewellAssetError("Generated farewell was not a canonical PCM WAV")
    finalized = bytearray(data)
    struct.pack_into("<I", finalized, 4, len(finalized) - 8)
    struct.pack_into("<I", finalized, 40, len(finalized) - 44)
    return bytes(finalized)


def _normalize_phrase(value: str) -> str:
    return "".join(character for character in value if character not in " \t\r\n，。！？,.!?")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def store_candidate(
    root: Path,
    *,
    label: str,
    wav_data: bytes,
    transcript: object,
    model: str,
    voice: str,
    output_gain: float,
    prompt_version: str = FAREWELL_PROMPT_VERSION,
) -> dict[str, object]:
    if not CANDIDATE_LABEL.fullmatch(label):
        raise RealtimeFarewellAssetError("Farewell candidate label was invalid")
    if not isinstance(transcript, str) or _normalize_phrase(transcript) != FAREWELL_PHRASE:
        raise RealtimeFarewellAssetError("Farewell transcript did not match 再见")
    try:
        normalized = trim_bounded_silence(
            wav_data,
            min_duration_ms=MIN_FAREWELL_DURATION_MS,
            max_duration_ms=MAX_FAREWELL_DURATION_MS,
        )
        info = inspect_wav(
            normalized,
            min_duration_ms=MIN_FAREWELL_DURATION_MS,
            max_duration_ms=MAX_FAREWELL_DURATION_MS,
        )
    except ValueError as exc:
        raise RealtimeFarewellAssetError(str(exc)) from exc
    digest = hashlib.sha256(normalized).hexdigest()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "phrase": FAREWELL_PHRASE,
        "prompt_version": prompt_version,
        "model": model,
        "voice": voice,
        "format": "wav_pcm_s16le_mono",
        "sample_rate": info.sample_rate,
        "duration_ms": info.duration_ms,
        "playback_gain": float(output_gain),
        "candidate": label,
        "sha256": digest,
    }
    root.mkdir(parents=True, exist_ok=True)
    audio_path = root / f"{label}.wav"
    manifest_path = root / f"{label}.json"
    _atomic_write(audio_path, normalized)
    _atomic_write(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    return {"audio_path": str(audio_path), "manifest_path": str(manifest_path), **manifest}


def load_selected_asset(audio_path: Path, manifest_path: Path) -> tuple[bytes, dict[str, object]]:
    if not audio_path.is_file() or not manifest_path.is_file():
        raise RealtimeFarewellAssetError("Cached Realtime farewell asset is missing")
    try:
        data = audio_path.read_bytes()
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RealtimeFarewellAssetError("Cached Realtime farewell asset could not be read") from exc
    if not isinstance(manifest, dict):
        raise RealtimeFarewellAssetError("Cached Realtime farewell manifest was invalid")
    try:
        info = inspect_wav(
            data,
            min_duration_ms=MIN_FAREWELL_DURATION_MS,
            max_duration_ms=MAX_FAREWELL_DURATION_MS,
        )
    except ValueError as exc:
        raise RealtimeFarewellAssetError(str(exc)) from exc
    expected = {
        "schema_version": 1,
        "phrase": FAREWELL_PHRASE,
        "format": "wav_pcm_s16le_mono",
        "sample_rate": info.sample_rate,
        "duration_ms": info.duration_ms,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RealtimeFarewellAssetError("Cached Realtime farewell manifest did not match its WAV")
    prompt_version = manifest.get("prompt_version")
    if not isinstance(prompt_version, str) or not prompt_version.startswith("mandarin-farewell-"):
        raise RealtimeFarewellAssetError("Cached Realtime farewell prompt version was invalid")
    if not isinstance(manifest.get("model"), str) or not isinstance(manifest.get("voice"), str):
        raise RealtimeFarewellAssetError("Cached Realtime farewell voice metadata was invalid")
    gain = manifest.get("playback_gain")
    if isinstance(gain, bool) or not isinstance(gain, (int, float)) or not 0 <= gain <= 1:
        raise RealtimeFarewellAssetError("Cached Realtime farewell gain was invalid")
    return data, manifest


def promote_candidate(candidate_audio: Path, *, project_root: Path, confirmed_by_owner: bool) -> dict[str, object]:
    if not confirmed_by_owner:
        raise RealtimeFarewellAssetError("Owner confirmation is required before promoting a farewell")
    data, manifest = load_selected_asset(candidate_audio, candidate_audio.with_suffix(".json"))
    destination = project_root / CANONICAL_FAREWELL_ASSET
    manifest_destination = project_root / CANONICAL_FAREWELL_MANIFEST
    selected = dict(manifest)
    selected["selected_by_owner"] = True
    _atomic_write(destination, data)
    _atomic_write(manifest_destination, (json.dumps(selected, ensure_ascii=False, indent=2) + "\n").encode())
    return {"audio_path": str(destination), "manifest_path": str(manifest_destination), **selected}

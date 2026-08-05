"""Validation and promotion for explicitly captured Realtime ACK assets."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import struct
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path


ACK_PHRASE = "嗯，我在，请说。"
ACK_PROMPT_VERSION = "mandarin-ready-v1"
MAX_CANDIDATE_BYTES = 1_500_000
MIN_DURATION_MS = 500
MAX_DURATION_MS = 6_000
SUPPORTED_SAMPLE_RATES = frozenset({16_000, 24_000, 32_000, 44_100, 48_000})
CANDIDATE_LABEL = re.compile(r"^candidate-[0-9]{2}$")
CANONICAL_ACK_ASSET = Path("assets/realtime_acknowledgement_alloy_zh.wav")
CANONICAL_ACK_MANIFEST = Path("assets/realtime_acknowledgement_alloy_zh.json")


class RealtimeAckAssetError(ValueError):
    pass


@dataclass(frozen=True)
class WavInfo:
    sample_rate: int
    channels: int
    frames: int
    duration_ms: int


def normalize_ack_phrase(value: str) -> str:
    return "".join(character for character in value if character not in " \t\r\n，。！？,.!?")


def validate_ack_transcript(value: object) -> None:
    if not isinstance(value, str) or normalize_ack_phrase(value) != normalize_ack_phrase(ACK_PHRASE):
        raise RealtimeAckAssetError("Realtime ACK transcript did not match the accepted phrase")


def inspect_wav(
    data: bytes,
    *,
    min_duration_ms: int = MIN_DURATION_MS,
    max_duration_ms: int = MAX_DURATION_MS,
) -> WavInfo:
    if not data or len(data) > MAX_CANDIDATE_BYTES:
        raise RealtimeAckAssetError("Realtime ACK candidate size was invalid")
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frames = audio.getnframes()
            compression = audio.getcomptype()
    except (EOFError, wave.Error) as exc:
        raise RealtimeAckAssetError("Realtime ACK candidate was not a valid WAV") from exc
    if channels != 1 or sample_width != 2 or compression != "NONE":
        raise RealtimeAckAssetError("Realtime ACK WAV must be mono 16-bit PCM")
    if sample_rate not in SUPPORTED_SAMPLE_RATES or frames <= 0:
        raise RealtimeAckAssetError("Realtime ACK WAV sample format was unsupported")
    duration_ms = round(frames * 1000 / sample_rate)
    if not min_duration_ms <= duration_ms <= max_duration_ms:
        raise RealtimeAckAssetError(
            f"Realtime WAV duration {duration_ms} ms was outside "
            f"{min_duration_ms}-{max_duration_ms} ms"
        )
    return WavInfo(sample_rate, channels, frames, duration_ms)


def trim_bounded_silence(
    data: bytes,
    *,
    threshold: int = 192,
    padding_ms: int = 40,
    min_duration_ms: int = MIN_DURATION_MS,
    max_duration_ms: int = MAX_DURATION_MS,
) -> bytes:
    """Trim digital silence while retaining a small natural boundary."""

    info = inspect_wav(data, min_duration_ms=min_duration_ms, max_duration_ms=max_duration_ms)
    with wave.open(io.BytesIO(data), "rb") as audio:
        pcm = audio.readframes(info.frames)
    samples = struct.unpack(f"<{info.frames}h", pcm)
    audible = [index for index, sample in enumerate(samples) if abs(sample) > threshold]
    if not audible:
        raise RealtimeAckAssetError("Realtime ACK candidate contained no audible samples")
    padding = round(info.sample_rate * padding_ms / 1000)
    start = max(0, audible[0] - padding)
    end = min(info.frames, audible[-1] + padding + 1)
    trimmed_pcm = struct.pack(f"<{end - start}h", *samples[start:end])
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(info.sample_rate)
        audio.writeframes(trimmed_pcm)
    trimmed = output.getvalue()
    inspect_wav(trimmed, min_duration_ms=min_duration_ms, max_duration_ms=max_duration_ms)
    return trimmed


def store_candidate(
    root: Path,
    *,
    label: str,
    wav_data: bytes,
    transcript: object,
    model: str,
    voice: str,
    output_gain: float,
) -> dict[str, object]:
    if not CANDIDATE_LABEL.fullmatch(label):
        raise RealtimeAckAssetError("Realtime ACK candidate label was invalid")
    validate_ack_transcript(transcript)
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", model) or not re.fullmatch(
        r"[A-Za-z0-9_.:-]{1,100}", voice
    ):
        raise RealtimeAckAssetError("Realtime ACK configuration identifier was invalid")
    if isinstance(output_gain, bool) or not isinstance(output_gain, (int, float)) or not 0 <= output_gain <= 1:
        raise RealtimeAckAssetError("Realtime ACK output gain was invalid")
    normalized = trim_bounded_silence(wav_data)
    info = inspect_wav(normalized)
    digest = hashlib.sha256(normalized).hexdigest()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "phrase": ACK_PHRASE,
        "prompt_version": ACK_PROMPT_VERSION,
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


def promote_candidate(
    candidate_audio: Path,
    *,
    project_root: Path,
    confirmed_by_owner: bool,
) -> dict[str, object]:
    if not confirmed_by_owner:
        raise RealtimeAckAssetError("Owner confirmation is required before promoting an ACK candidate")
    candidate_manifest = candidate_audio.with_suffix(".json")
    if not candidate_audio.is_file() or not candidate_manifest.is_file():
        raise RealtimeAckAssetError("Realtime ACK candidate or manifest was missing")
    data = candidate_audio.read_bytes()
    info = inspect_wav(data)
    try:
        manifest = json.loads(candidate_manifest.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RealtimeAckAssetError("Realtime ACK candidate manifest was invalid") from exc
    required = {
        "schema_version", "phrase", "prompt_version", "model", "voice", "format",
        "sample_rate", "duration_ms", "playback_gain", "candidate", "sha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise RealtimeAckAssetError("Realtime ACK candidate manifest fields were invalid")
    validate_ack_transcript(manifest.get("phrase"))
    if manifest.get("duration_ms") != info.duration_ms or manifest.get("sample_rate") != info.sample_rate:
        raise RealtimeAckAssetError("Realtime ACK candidate manifest did not match its WAV")
    if manifest.get("sha256") != hashlib.sha256(data).hexdigest():
        raise RealtimeAckAssetError("Realtime ACK candidate digest did not match")
    destination = project_root / CANONICAL_ACK_ASSET
    manifest_destination = project_root / CANONICAL_ACK_MANIFEST
    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(destination, data)
    promoted = dict(manifest)
    promoted["selected_by_owner"] = True
    _atomic_write(
        manifest_destination,
        (json.dumps(promoted, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    return {"audio_path": str(destination), "manifest_path": str(manifest_destination), **promoted}


def prepare_selected_asset(
    *,
    project_root: Path,
    destination: Path,
) -> dict[str, object]:
    source = project_root / CANONICAL_ACK_ASSET
    manifest_path = project_root / CANONICAL_ACK_MANIFEST
    data, manifest = load_selected_asset(source, manifest_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(destination, data)
    return {"audio_path": str(destination), **manifest}


def load_selected_asset(
    source: Path,
    manifest_path: Path,
) -> tuple[bytes, dict[str, object]]:
    """Load an owner-selected ACK only after complete manifest verification."""

    if not source.is_file() or not manifest_path.is_file():
        raise RealtimeAckAssetError("Selected Realtime ACK asset is missing; capture and promote one first")
    data = source.read_bytes()
    info = inspect_wav(data)
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RealtimeAckAssetError("Selected Realtime ACK manifest was invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("selected_by_owner") is not True:
        raise RealtimeAckAssetError("Selected Realtime ACK lacks owner confirmation")
    if manifest.get("sha256") != hashlib.sha256(data).hexdigest():
        raise RealtimeAckAssetError("Selected Realtime ACK digest did not match")
    if manifest.get("duration_ms") != info.duration_ms or manifest.get("sample_rate") != info.sample_rate:
        raise RealtimeAckAssetError("Selected Realtime ACK manifest did not match its WAV")
    playback_gain = manifest.get("playback_gain")
    if (
        isinstance(playback_gain, bool)
        or not isinstance(playback_gain, (int, float))
        or not 0 <= playback_gain <= 1
    ):
        raise RealtimeAckAssetError("Selected Realtime ACK playback gain was invalid")
    return data, dict(manifest)


def _atomic_write(path: Path, data: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{path.name}-", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

"""Validation, selection, and preparation for cached English voice cues."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from .realtime_ack_asset import inspect_wav, trim_bounded_silence


MODEL = "gpt-4o-mini-tts"
VOICE = "alloy"
LOCALE = "en"
SAMPLE_RATE = 24_000
PLAYBACK_GAIN = 0.5
CANDIDATE_LABEL = re.compile(r"^candidate-[0-9]{2}$")


@dataclass(frozen=True)
class CueSpec:
    name: str
    phrase: str
    min_duration_ms: int
    max_duration_ms: int
    canonical_audio: Path
    canonical_manifest: Path


CUES = {
    "ack": CueSpec(
        "ack",
        "I'm here. Yes?",
        300,
        3_000,
        Path("assets/realtime_acknowledgement_alloy_en.wav"),
        Path("assets/realtime_acknowledgement_alloy_en.json"),
    ),
    "farewell": CueSpec(
        "farewell",
        "See you.",
        150,
        2_000,
        Path("assets/realtime_farewell_alloy_en.wav"),
        Path("assets/realtime_farewell_alloy_en.json"),
    ),
}


class EnglishVoiceCueError(ValueError):
    pass


def cue_spec(name: str) -> CueSpec:
    try:
        return CUES[name]
    except KeyError as exc:
        raise EnglishVoiceCueError("English cue name was invalid") from exc


def normalize_phrase(value: str) -> str:
    return "".join(character.lower() for character in value if character not in " \t\r\n,.!?")


def _silence_ms(data: bytes, *, threshold: int = 192) -> tuple[int, int]:
    with wave.open(PathLikeBytes(data), "rb") as audio:
        rate = audio.getframerate()
        frames = audio.getnframes()
        samples = struct.unpack(f"<{frames}h", audio.readframes(frames))
    audible = [index for index, sample in enumerate(samples) if abs(sample) > threshold]
    if not audible:
        raise EnglishVoiceCueError("English cue contained no audible samples")
    return round(audible[0] * 1000 / rate), round((frames - audible[-1] - 1) * 1000 / rate)


class PathLikeBytes:
    """Small seekable bytes wrapper accepted by wave.open without exporting io."""

    def __init__(self, data: bytes):
        import io

        self._buffer = io.BytesIO(data)

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._buffer.seek(offset, whence)

    def tell(self) -> int:
        return self._buffer.tell()

    def close(self) -> None:
        self._buffer.close()


def store_candidate(
    root: Path,
    *,
    cue: str,
    label: str,
    wav_data: bytes,
    transcript: object,
    prompt_version: str,
    model: str = MODEL,
    voice: str = VOICE,
    output_gain: float = PLAYBACK_GAIN,
) -> dict[str, object]:
    spec = cue_spec(cue)
    if not CANDIDATE_LABEL.fullmatch(label):
        raise EnglishVoiceCueError("English cue candidate label was invalid")
    if not isinstance(transcript, str) or normalize_phrase(transcript) != normalize_phrase(spec.phrase):
        raise EnglishVoiceCueError("English cue transcript did not match the intended phrase")
    if model != MODEL or voice != VOICE or output_gain != PLAYBACK_GAIN:
        raise EnglishVoiceCueError("English cue voice configuration was invalid")
    if not re.fullmatch(r"english-(ack|farewell)-[a-z0-9-]+-v1", prompt_version):
        raise EnglishVoiceCueError("English cue prompt version was invalid")
    try:
        normalized = trim_bounded_silence(
            wav_data,
            min_duration_ms=spec.min_duration_ms,
            max_duration_ms=spec.max_duration_ms,
        )
        info = inspect_wav(
            normalized,
            min_duration_ms=spec.min_duration_ms,
            max_duration_ms=spec.max_duration_ms,
        )
    except ValueError as exc:
        raise EnglishVoiceCueError(str(exc)) from exc
    if info.sample_rate != SAMPLE_RATE:
        raise EnglishVoiceCueError("English cue WAV must use 24 kHz PCM")
    leading_ms, trailing_ms = _silence_ms(normalized)
    if leading_ms > 80 or trailing_ms > 80:
        raise EnglishVoiceCueError("English cue silence boundary was unsafe")
    digest = hashlib.sha256(normalized).hexdigest()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "cue": cue,
        "locale": LOCALE,
        "phrase": spec.phrase,
        "prompt_version": prompt_version,
        "model": model,
        "voice": voice,
        "format": "wav_pcm_s16le_mono",
        "sample_rate": info.sample_rate,
        "duration_ms": info.duration_ms,
        "leading_silence_ms": leading_ms,
        "trailing_silence_ms": trailing_ms,
        "playback_gain": output_gain,
        "candidate": label,
        "sha256": digest,
    }
    destination = root / cue
    audio_path = destination / f"{label}.wav"
    manifest_path = destination / f"{label}.json"
    _atomic_write(audio_path, normalized)
    _atomic_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode())
    return {"audio_path": str(audio_path), "manifest_path": str(manifest_path), **manifest}


def load_candidate(audio_path: Path, *, selected_required: bool = False) -> tuple[bytes, dict[str, object]]:
    manifest_path = audio_path.with_suffix(".json")
    if not audio_path.is_file() or not manifest_path.is_file():
        raise EnglishVoiceCueError("English cue audio or manifest was missing")
    try:
        data = audio_path.read_bytes()
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise EnglishVoiceCueError("English cue could not be read") from exc
    if not isinstance(manifest, dict):
        raise EnglishVoiceCueError("English cue manifest was invalid")
    spec = cue_spec(str(manifest.get("cue", "")))
    required = {
        "schema_version", "cue", "locale", "phrase", "prompt_version", "model", "voice",
        "format", "sample_rate", "duration_ms", "leading_silence_ms", "trailing_silence_ms",
        "playback_gain", "candidate", "sha256",
    }
    if selected_required:
        required.add("selected_by_owner")
    if set(manifest) != required:
        raise EnglishVoiceCueError("English cue manifest fields were invalid")
    try:
        info = inspect_wav(data, min_duration_ms=spec.min_duration_ms, max_duration_ms=spec.max_duration_ms)
    except ValueError as exc:
        raise EnglishVoiceCueError(str(exc)) from exc
    expected = {
        "schema_version": 1,
        "locale": LOCALE,
        "phrase": spec.phrase,
        "model": MODEL,
        "voice": VOICE,
        "format": "wav_pcm_s16le_mono",
        "sample_rate": SAMPLE_RATE,
        "duration_ms": info.duration_ms,
        "playback_gain": PLAYBACK_GAIN,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise EnglishVoiceCueError("English cue manifest did not match its WAV")
    if selected_required and manifest.get("selected_by_owner") is not True:
        raise EnglishVoiceCueError("English cue lacks owner selection")
    leading_ms, trailing_ms = _silence_ms(data)
    if manifest.get("leading_silence_ms") != leading_ms or manifest.get("trailing_silence_ms") != trailing_ms:
        raise EnglishVoiceCueError("English cue silence metadata did not match")
    return data, manifest


def promote_candidate(audio_path: Path, *, project_root: Path, confirmed_by_owner: bool) -> dict[str, object]:
    if not confirmed_by_owner:
        raise EnglishVoiceCueError("Owner confirmation is required before promotion")
    data, manifest = load_candidate(audio_path)
    spec = cue_spec(str(manifest["cue"]))
    selected = dict(manifest)
    selected["selected_by_owner"] = True
    _atomic_write(project_root / spec.canonical_audio, data)
    _atomic_write(
        project_root / spec.canonical_manifest,
        (json.dumps(selected, indent=2) + "\n").encode(),
    )
    return {"audio_path": str(project_root / spec.canonical_audio), **selected}


def prepare_selected_assets(*, project_root: Path, destination: Path) -> dict[str, object]:
    prepared: dict[str, object] = {}
    for cue, spec in CUES.items():
        data, manifest = load_candidate(project_root / spec.canonical_audio, selected_required=True)
        audio_target = destination / spec.canonical_audio.name
        manifest_target = destination / spec.canonical_manifest.name
        _atomic_write(audio_target, data)
        _atomic_write(manifest_target, (json.dumps(manifest, indent=2) + "\n").encode())
        prepared[cue] = {
            "audio_path": str(audio_target),
            "manifest_path": str(manifest_target),
            **manifest,
        }
    return prepared


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

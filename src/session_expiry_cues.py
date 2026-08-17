"""Candidate validation and owner-gated promotion for session-expiry cues."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import struct
import tempfile
import wave
from pathlib import Path

from .realtime_ack_asset import inspect_wav, trim_bounded_silence


MODEL = "gpt-4o-mini-tts"
VOICE = "alloy"
SAMPLE_RATE = 24_000
PLAYBACK_GAIN = 0.5
WARNING_MIN_MS = 2_000
WARNING_MAX_MS = 15_000
TONE_MIN_MS = 250
TONE_MAX_MS = 1_500
LABELS = ("candidate-01", "candidate-02", "candidate-03")
LABEL_PATTERN = re.compile(r"^candidate-0[1-3]$")
WARNING_PHRASES = {
    "en": "This conversation is about to end. When you hear the tone, say ‘Hey Jarvis’ to start a new one.",
    "zh-CN": "本轮对话即将结束。结束后，听到提示音，再说“Hey Jarvis”即可开始新一轮对话。",
}
CANONICAL_ASSETS = {
    "en": Path("assets/session_expiry_warning_alloy_en.wav"),
    "zh-CN": Path("assets/session_expiry_warning_alloy_zh.wav"),
    "ready": Path("assets/realtime_ready_chime.wav"),
}


class SessionExpiryCueError(ValueError):
    pass


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


def _normalized_phrase(value: str) -> str:
    ignored = " \t\r\n,.!?，。！？‘’“”'\""
    return "".join(character.lower() for character in value if character not in ignored)


def _wav_samples(data: bytes) -> tuple[int, tuple[int, ...]]:
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            rate = audio.getframerate()
            frames = audio.getnframes()
            samples = struct.unpack(f"<{frames}h", audio.readframes(frames))
    except (EOFError, wave.Error, struct.error) as exc:
        raise SessionExpiryCueError("Session cue was not valid PCM WAV") from exc
    return rate, samples


def _signal_metadata(data: bytes) -> tuple[int, int, int]:
    rate, samples = _wav_samples(data)
    audible = [index for index, sample in enumerate(samples) if abs(sample) > 192]
    if not audible:
        raise SessionExpiryCueError("Session cue contained no audible samples")
    if any(abs(sample) >= 32_767 for sample in samples):
        raise SessionExpiryCueError("Session cue contained clipped samples")
    leading_ms = round(audible[0] * 1000 / rate)
    trailing_ms = round((len(samples) - audible[-1] - 1) * 1000 / rate)
    return leading_ms, trailing_ms, max(abs(sample) for sample in samples)


def _candidate_paths(root: Path, kind: str, locale: str, label: str) -> tuple[Path, Path]:
    directory = root / (f"warning-{locale}" if kind == "warning" else "ready-tone")
    return directory / f"{label}.wav", directory / f"{label}.json"


def store_warning_candidate(
    root: Path,
    *,
    locale: str,
    label: str,
    wav_data: bytes,
    transcript: object,
    prompt_version: str,
) -> dict[str, object]:
    if locale not in WARNING_PHRASES or not LABEL_PATTERN.fullmatch(label):
        raise SessionExpiryCueError("Session warning locale or candidate was invalid")
    phrase = WARNING_PHRASES[locale]
    if not isinstance(transcript, str) or _normalized_phrase(transcript) != _normalized_phrase(phrase):
        raise SessionExpiryCueError("Session warning transcript did not match the fixed phrase")
    if not re.fullmatch(r"session-expiry-(en|zh)-[a-z-]+-v1", prompt_version):
        raise SessionExpiryCueError("Session warning prompt version was invalid")
    try:
        normalized = trim_bounded_silence(
            wav_data,
            min_duration_ms=WARNING_MIN_MS,
            max_duration_ms=WARNING_MAX_MS,
        )
        info = inspect_wav(
            normalized,
            min_duration_ms=WARNING_MIN_MS,
            max_duration_ms=WARNING_MAX_MS,
        )
    except ValueError as exc:
        raise SessionExpiryCueError(str(exc)) from exc
    if info.sample_rate != SAMPLE_RATE:
        raise SessionExpiryCueError("Session warning must use 24 kHz PCM")
    leading_ms, trailing_ms, peak = _signal_metadata(normalized)
    if leading_ms > 80 or trailing_ms > 80:
        raise SessionExpiryCueError("Session warning silence boundary was unsafe")
    return _store(
        root,
        kind="warning",
        locale=locale,
        label=label,
        data=normalized,
        duration_ms=info.duration_ms,
        leading_ms=leading_ms,
        trailing_ms=trailing_ms,
        peak=peak,
        phrase=phrase,
        prompt_version=prompt_version,
        source="openai_tts",
        model=MODEL,
        voice=VOICE,
    )


def _tone_wav(notes: tuple[tuple[float, int], ...]) -> bytes:
    samples: list[int] = []
    amplitude = 8_200
    fade_frames = round(SAMPLE_RATE * 0.025)
    gap_frames = round(SAMPLE_RATE * 0.035)
    for note_index, (frequency, duration_ms) in enumerate(notes):
        frames = round(SAMPLE_RATE * duration_ms / 1000)
        for index in range(frames):
            envelope = min(1.0, index / fade_frames, (frames - index - 1) / fade_frames)
            fundamental = math.sin(2 * math.pi * frequency * index / SAMPLE_RATE)
            harmonic = 0.16 * math.sin(4 * math.pi * frequency * index / SAMPLE_RATE)
            samples.append(round(amplitude * max(0.0, envelope) * (fundamental + harmonic)))
        if note_index + 1 < len(notes):
            samples.extend([0] * gap_frames)
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output.getvalue()


TONE_PATTERNS = {
    "candidate-01": ((659.25, 180), (880.00, 260)),
    "candidate-02": ((523.25, 150), (659.25, 150), (783.99, 260)),
    "candidate-03": ((587.33, 210), (783.99, 310)),
}


def synthesize_ready_tones(root: Path) -> list[dict[str, object]]:
    results = []
    for label in LABELS:
        data = _tone_wav(TONE_PATTERNS[label])
        info = inspect_wav(data, min_duration_ms=TONE_MIN_MS, max_duration_ms=TONE_MAX_MS)
        leading_ms, trailing_ms, peak = _signal_metadata(data)
        results.append(
            _store(
                root,
                kind="ready",
                locale="und",
                label=label,
                data=data,
                duration_ms=info.duration_ms,
                leading_ms=leading_ms,
                trailing_ms=trailing_ms,
                peak=peak,
                phrase=None,
                prompt_version=f"ready-chime-local-{label[-2:]}-v1",
                source="local_synthesis",
                model="deterministic-sine-v1",
                voice="none",
            )
        )
    return results


def _store(
    root: Path,
    *,
    kind: str,
    locale: str,
    label: str,
    data: bytes,
    duration_ms: int,
    leading_ms: int,
    trailing_ms: int,
    peak: int,
    phrase: str | None,
    prompt_version: str,
    source: str,
    model: str,
    voice: str,
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": 1,
        "kind": kind,
        "locale": locale,
        "phrase": phrase,
        "prompt_version": prompt_version,
        "source": source,
        "model": model,
        "voice": voice,
        "format": "wav_pcm_s16le_mono",
        "sample_rate": SAMPLE_RATE,
        "duration_ms": duration_ms,
        "leading_silence_ms": leading_ms,
        "trailing_silence_ms": trailing_ms,
        "peak_sample": peak,
        "playback_gain": PLAYBACK_GAIN,
        "candidate": label,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    audio_path, manifest_path = _candidate_paths(root, kind, locale, label)
    _atomic_write(audio_path, data)
    _atomic_write(
        manifest_path,
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    return {"audio_path": str(audio_path), "manifest_path": str(manifest_path), **manifest}


def load_candidate(audio_path: Path) -> tuple[bytes, dict[str, object]]:
    manifest_path = audio_path.with_suffix(".json")
    try:
        data = audio_path.read_bytes()
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionExpiryCueError("Session cue audio or manifest was unreadable") from exc
    data, manifest = _validate_cue(data, manifest)
    label = manifest["candidate"]
    kind = manifest["kind"]
    locale = manifest["locale"]
    expected_audio, _ = _candidate_paths(audio_path.parents[1], kind, locale, label)
    if audio_path != expected_audio:
        raise SessionExpiryCueError("Session cue path did not match its identity")
    return data, manifest


def load_selected_asset(audio_path: Path, *, expected_slot: str) -> tuple[bytes, dict[str, object]]:
    """Load one canonical cue only after owner selection and full validation."""

    try:
        data = audio_path.read_bytes()
        manifest = json.loads(audio_path.with_suffix(".json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionExpiryCueError("Selected session cue was unreadable") from exc
    if not isinstance(manifest, dict) or manifest.get("selected_by_owner") is not True:
        raise SessionExpiryCueError("Selected session cue lacks owner confirmation")
    candidate_manifest = dict(manifest)
    candidate_manifest.pop("selected_by_owner", None)
    data, candidate_manifest = _validate_cue(data, candidate_manifest)
    actual_slot = (
        "ready" if candidate_manifest["kind"] == "ready" else candidate_manifest["locale"]
    )
    if expected_slot not in CANONICAL_ASSETS or actual_slot != expected_slot:
        raise SessionExpiryCueError("Selected session cue did not match its runtime slot")
    return data, dict(manifest)


def _validate_cue(
    data: bytes, manifest: object
) -> tuple[bytes, dict[str, object]]:
    required = {
        "schema_version", "kind", "locale", "phrase", "prompt_version", "source", "model",
        "voice", "format", "sample_rate", "duration_ms", "leading_silence_ms",
        "trailing_silence_ms", "peak_sample", "playback_gain", "candidate", "sha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise SessionExpiryCueError("Session cue manifest fields were invalid")
    kind = manifest.get("kind")
    minimum, maximum = (
        (WARNING_MIN_MS, WARNING_MAX_MS) if kind == "warning" else (TONE_MIN_MS, TONE_MAX_MS)
    )
    if kind not in {"warning", "ready"}:
        raise SessionExpiryCueError("Session cue kind was invalid")
    try:
        info = inspect_wav(data, min_duration_ms=minimum, max_duration_ms=maximum)
    except ValueError as exc:
        raise SessionExpiryCueError(str(exc)) from exc
    leading_ms, trailing_ms, peak = _signal_metadata(data)
    expected = {
        "schema_version": 1,
        "format": "wav_pcm_s16le_mono",
        "sample_rate": SAMPLE_RATE,
        "duration_ms": info.duration_ms,
        "leading_silence_ms": leading_ms,
        "trailing_silence_ms": trailing_ms,
        "peak_sample": peak,
        "playback_gain": PLAYBACK_GAIN,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise SessionExpiryCueError("Session cue manifest did not match its WAV")
    label = manifest.get("candidate")
    locale = manifest.get("locale")
    if not isinstance(label, str) or not LABEL_PATTERN.fullmatch(label):
        raise SessionExpiryCueError("Session cue candidate label was invalid")
    if kind == "warning":
        if locale not in WARNING_PHRASES or manifest.get("phrase") != WARNING_PHRASES[locale]:
            raise SessionExpiryCueError("Session warning locale or phrase was invalid")
        if manifest.get("source") != "openai_tts" or manifest.get("model") != MODEL or manifest.get("voice") != VOICE:
            raise SessionExpiryCueError("Session warning generation metadata was invalid")
    elif locale != "und" or manifest.get("phrase") is not None or manifest.get("source") != "local_synthesis":
        raise SessionExpiryCueError("Ready tone metadata was invalid")
    return data, manifest


def promote_selection(
    *,
    project_root: Path,
    english: Path,
    chinese: Path,
    ready: Path,
    confirmed_by_owner: bool,
) -> dict[str, object]:
    if not confirmed_by_owner:
        raise SessionExpiryCueError("Owner confirmation is required before cue promotion")
    selections = {"en": english, "zh-CN": chinese, "ready": ready}
    promoted: dict[str, object] = {}
    for expected, source in selections.items():
        data, manifest = load_candidate(source)
        actual = "ready" if manifest["kind"] == "ready" else manifest["locale"]
        if actual != expected:
            raise SessionExpiryCueError("Selected session cue did not match its promotion slot")
        target = project_root / CANONICAL_ASSETS[expected]
        selected = dict(manifest)
        selected["selected_by_owner"] = True
        _atomic_write(target, data)
        _atomic_write(
            target.with_suffix(".json"),
            (json.dumps(selected, ensure_ascii=False, indent=2) + "\n").encode(),
        )
        promoted[expected] = {"audio_path": str(target), **selected}
    return promoted

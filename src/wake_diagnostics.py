"""Bounded, content-free wake-word tuning diagnostics."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .wake_word import pcm_rms_and_peak


WAKE_DIAGNOSTIC_SCHEMA = "hey-jarvis-wake-v1"
WAKE_DIAGNOSTIC_LIMIT_BYTES = 512 * 1024
WAKE_DIAGNOSTIC_GENERATIONS = 3
WAKE_DIAGNOSTIC_FILENAME = "wake.jsonl"
WAKE_DIAGNOSTIC_EVENTS = frozenset(
    {"near_threshold", "positive", "reset", "confirmed", "overflow"}
)
APP_PREFERENCES_VERSION = 5
APP_WAKE_THRESHOLDS = frozenset({0.5, 0.6})
APP_WAKE_CONFIRMATION_FRAMES = frozenset({2, 3})


@dataclass(frozen=True)
class AppWakePreferences:
    diagnostics_enabled: bool = False
    threshold: float = 0.5
    confirmation_frames: int = 2


class WakeDiagnostics:
    """Write only allowlisted numeric evidence; failures never affect listening."""

    def __init__(
        self,
        app_support_dir: Path | None = None,
        *,
        diagnostics_dir: Path | None = None,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
        limit_bytes: int = WAKE_DIAGNOSTIC_LIMIT_BYTES,
        generations: int = WAKE_DIAGNOSTIC_GENERATIONS,
    ) -> None:
        if limit_bytes <= 0 or generations < 1:
            raise ValueError("wake diagnostic retention bounds must be positive")
        if (app_support_dir is None) == (diagnostics_dir is None):
            raise ValueError("provide exactly one wake diagnostic storage root")
        if diagnostics_dir is not None:
            self.root = diagnostics_dir
        else:
            assert app_support_dir is not None
            self.root = app_support_dir / "diagnostics"
        self.path = self.root / WAKE_DIAGNOSTIC_FILENAME
        self._clock_ms = clock_ms
        self._limit_bytes = limit_bytes
        self._generations = generations

    def observe(
        self,
        pcm_chunk: bytes,
        *,
        event: str,
        score: float,
        threshold: float,
        consecutive: int,
        required: int,
        overflowed: bool,
    ) -> None:
        if event not in WAKE_DIAGNOSTIC_EVENTS:
            return
        if not all(math.isfinite(value) for value in (score, threshold)):
            return
        if not 0.0 <= score <= 1.0 or not 0.0 <= threshold <= 1.0:
            return
        if consecutive < 0 or required < 1 or consecutive > required:
            return
        try:
            rms, peak = pcm_rms_and_peak(pcm_chunk)
        except (TypeError, ValueError):
            return
        record = {
            "schema": WAKE_DIAGNOSTIC_SCHEMA,
            "at_ms": int(self._clock_ms()),
            "event": event,
            "score": round(score, 9),
            "threshold": round(threshold, 9),
            "consecutive": consecutive,
            "required": required,
            "rms": round(rms, 1),
            "peak": peak,
            "overflow": bool(overflowed),
        }
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        except OSError:
            return

    def _rotate_if_needed(self) -> None:
        if not self.path.exists() or self.path.stat().st_size < self._limit_bytes:
            return
        for generation in range(self._generations - 1, 0, -1):
            source = self.path.with_suffix(f".jsonl.{generation}")
            target = self.path.with_suffix(f".jsonl.{generation + 1}")
            if source.exists():
                source.replace(target)
        self.path.replace(self.path.with_suffix(".jsonl.1"))


def load_app_wake_preferences(preferences_path: Path) -> AppWakePreferences:
    """Read the native schema exactly; a missing first-run file uses safe defaults."""

    try:
        value = json.loads(preferences_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AppWakePreferences()
    except (OSError, json.JSONDecodeError, UnicodeError):
        raise ValueError("preferences_corrupt") from None
    if not isinstance(value, dict) or set(value) != {
        "version",
        "smart_speaker_mode",
        "app_language",
        "app_theme",
        "wake_diagnostics_enabled",
        "wake_threshold",
        "wake_confirmation_frames",
    }:
        raise ValueError("preferences_corrupt")
    threshold = value.get("wake_threshold")
    frames = value.get("wake_confirmation_frames")
    valid = (
        type(value.get("version")) is int
        and value["version"] == APP_PREFERENCES_VERSION
        and type(value.get("smart_speaker_mode")) is bool
        and value.get("app_language") in {"en", "zh-CN"}
        and value.get("app_theme") in {"night", "day"}
        and type(value.get("wake_diagnostics_enabled")) is bool
        and type(threshold) is float
        and threshold in APP_WAKE_THRESHOLDS
        and type(frames) is int
        and frames in APP_WAKE_CONFIRMATION_FRAMES
    )
    if not valid:
        raise ValueError("preferences_corrupt")
    return AppWakePreferences(
        diagnostics_enabled=value["wake_diagnostics_enabled"],
        threshold=threshold,
        confirmation_frames=frames,
    )


def wake_diagnostics_enabled(preferences_path: Path) -> bool:
    """Fail closed unless the current native preference is valid and enabled."""

    try:
        return load_app_wake_preferences(preferences_path).diagnostics_enabled
    except ValueError:
        return False

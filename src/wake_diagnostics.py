"""Bounded, content-free wake-word tuning diagnostics."""

from __future__ import annotations

import json
import math
import time
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


class WakeDiagnostics:
    """Write only allowlisted numeric evidence; failures never affect listening."""

    def __init__(
        self,
        app_support_dir: Path,
        *,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
        limit_bytes: int = WAKE_DIAGNOSTIC_LIMIT_BYTES,
        generations: int = WAKE_DIAGNOSTIC_GENERATIONS,
    ) -> None:
        if limit_bytes <= 0 or generations < 1:
            raise ValueError("wake diagnostic retention bounds must be positive")
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


def wake_diagnostics_enabled(preferences_path: Path) -> bool:
    """Fail closed unless the current native preference is an exact boolean."""

    try:
        value = json.loads(preferences_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return False
    if not isinstance(value, dict) or set(value) != {
        "version",
        "smart_speaker_mode",
        "app_language",
        "app_theme",
        "wake_diagnostics_enabled",
    }:
        return False
    return (
        type(value.get("version")) is int
        and value["version"] == 4
        and type(value.get("smart_speaker_mode")) is bool
        and value.get("app_language") in {"en", "zh-CN"}
        and value.get("app_theme") in {"night", "day"}
        and value.get("wake_diagnostics_enabled") is True
    )

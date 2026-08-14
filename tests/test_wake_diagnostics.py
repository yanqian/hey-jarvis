from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from src.wake_diagnostics import (
    WakeDiagnostics,
    load_app_wake_preferences,
    wake_diagnostics_enabled,
)


def pcm(*samples: int) -> bytes:
    return b"".join(struct.pack("<h", sample) for sample in samples)


class WakeDiagnosticsTests(unittest.TestCase):
    def test_app_and_cli_storage_modes_emit_equivalent_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = WakeDiagnostics(root / "app-support", clock_ms=lambda: 42)
            cli = WakeDiagnostics(diagnostics_dir=root / "cli-output", clock_ms=lambda: 42)
            for diagnostics in (app, cli):
                diagnostics.observe(
                    pcm(100, -100),
                    event="confirmed",
                    score=0.61,
                    threshold=0.6,
                    consecutive=3,
                    required=3,
                    overflowed=False,
                )
            app_record = json.loads(app.path.read_text(encoding="utf-8"))
            cli_record = json.loads(cli.path.read_text(encoding="utf-8"))
            self.assertEqual(app_record, cli_record)
            self.assertEqual(app.path.name, "wake.jsonl")
            self.assertEqual(cli.path.name, "wake.jsonl")

    def test_writer_records_only_bounded_numeric_allowlisted_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            diagnostics = WakeDiagnostics(Path(directory), clock_ms=lambda: 1234)
            diagnostics.observe(
                pcm(100, -100),
                event="positive",
                score=0.61,
                threshold=0.6,
                consecutive=1,
                required=2,
                overflowed=False,
            )
            record = json.loads(diagnostics.path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(record),
                {
                    "schema",
                    "at_ms",
                    "event",
                    "score",
                    "threshold",
                    "consecutive",
                    "required",
                    "rms",
                    "peak",
                    "overflow",
                },
            )
            self.assertEqual(record["at_ms"], 1234)
            self.assertEqual(record["score"], 0.61)
            self.assertNotIn("audio", record)
            self.assertNotIn("transcript", record)

    def test_invalid_events_values_and_write_failures_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diagnostics = WakeDiagnostics(root)
            for event, score in (("conversation", 0.7), ("positive", float("nan"))):
                diagnostics.observe(
                    pcm(1),
                    event=event,
                    score=score,
                    threshold=0.5,
                    consecutive=1,
                    required=2,
                    overflowed=False,
                )
            self.assertFalse(diagnostics.path.exists())

            blocked = root / "blocked"
            blocked.write_text("not a directory", encoding="utf-8")
            WakeDiagnostics(blocked).observe(
                pcm(1),
                event="positive",
                score=0.7,
                threshold=0.5,
                consecutive=1,
                required=2,
                overflowed=False,
            )

    def test_rotation_keeps_only_bounded_generations(self):
        with tempfile.TemporaryDirectory() as directory:
            diagnostics = WakeDiagnostics(Path(directory), limit_bytes=1, generations=2)
            for at_ms in range(4):
                diagnostics._clock_ms = lambda value=at_ms: value
                diagnostics.observe(
                    pcm(100),
                    event="near_threshold",
                    score=0.3,
                    threshold=0.5,
                    consecutive=0,
                    required=2,
                    overflowed=False,
                )
            self.assertTrue(diagnostics.path.exists())
            self.assertTrue(diagnostics.path.with_suffix(".jsonl.1").exists())
            self.assertTrue(diagnostics.path.with_suffix(".jsonl.2").exists())
            self.assertFalse(diagnostics.path.with_suffix(".jsonl.3").exists())

    def test_preference_parser_fails_closed_and_accepts_only_current_true_boolean(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences-v1.json"
            self.assertFalse(wake_diagnostics_enabled(path))
            for value in (
                {"version": 3, "wake_diagnostics_enabled": True},
                {"version": 4, "wake_diagnostics_enabled": "true"},
                {"version": 5, "wake_diagnostics_enabled": False},
            ):
                path.write_text(json.dumps(value), encoding="utf-8")
                self.assertFalse(wake_diagnostics_enabled(path))
            path.write_text(
                json.dumps({
                    "version": 5,
                    "smart_speaker_mode": False,
                    "app_language": "en",
                    "app_theme": "night",
                    "wake_diagnostics_enabled": True,
                    "wake_threshold": 0.6,
                    "wake_confirmation_frames": 3,
                }),
                encoding="utf-8",
            )
            self.assertTrue(wake_diagnostics_enabled(path))
            preferences = load_app_wake_preferences(path)
            self.assertEqual(preferences.threshold, 0.6)
            self.assertEqual(preferences.confirmation_frames, 3)
            for field, invalid in (
                ("wake_threshold", True),
                ("wake_threshold", "0.6"),
                ("wake_threshold", 0.55),
                ("wake_confirmation_frames", True),
                ("wake_confirmation_frames", "3"),
                ("wake_confirmation_frames", 4),
            ):
                value = {
                    "version": 5,
                    "smart_speaker_mode": False,
                    "app_language": "en",
                    "app_theme": "night",
                    "wake_diagnostics_enabled": True,
                    "wake_threshold": 0.6,
                    "wake_confirmation_frames": 3,
                }
                value[field] = invalid
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "preferences_corrupt"):
                    load_app_wake_preferences(path)
                self.assertFalse(wake_diagnostics_enabled(path))


if __name__ == "__main__":
    unittest.main()

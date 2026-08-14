import json
import tempfile
import unittest
from pathlib import Path

from scripts.startup_report import ReportError, load_records, summarize


def record(launch: str, stage: str, elapsed: int, *, profile: str = "release", sample: str = "warm"):
    return {
        "schema": "hey-jarvis-startup-v1",
        "launch_id": launch,
        "build_profile": profile,
        "sample_kind": sample,
        "component": "native",
        "stage": stage,
        "receipt_elapsed_ms": elapsed,
        "process_elapsed_ms": None,
    }


class StartupReportTests(unittest.TestCase):
    def test_reports_median_and_nearest_rank_p90(self):
        rows = [record(f"launch-{index}", "window_shown", value) for index, value in enumerate([100, 200, 300, 400, 900], 1)]
        report = summarize(rows, "release", "warm")
        stage = report["stages"]["native.window_shown.receipt"]
        self.assertEqual(stage, {"count": 5, "median_ms": 300, "p90_ms": 900, "max_ms": 900})

    def test_latest_selects_complete_launches_in_input_order(self):
        rows = [
            record(f"launch-{index}", "window_shown", value)
            for index, value in enumerate([100, 200, 300], 1)
        ]
        report = summarize(rows, "release", "warm", latest=2)
        self.assertEqual(report["launches"], 2)
        self.assertEqual(report["stages"]["native.window_shown.receipt"]["median_ms"], 250)

    def test_rejects_mixed_definitions_and_duplicate_stages(self):
        with self.assertRaisesRegex(ReportError, "mixed"):
            summarize([record("launch-1", "window_shown", 1), record("launch-2", "window_shown", 2, profile="debug")], None, "warm")
        with self.assertRaisesRegex(ReportError, "duplicate"):
            summarize([record("launch-1", "window_shown", 1), record("launch-1", "window_shown", 2)], "release", "warm")

    def test_loader_rejects_unknown_or_unbounded_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.jsonl"
            bad = record("launch-1", "window_shown", 300_001)
            bad["transcript"] = "forbidden"
            path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            with self.assertRaises(ReportError):
                load_records([path])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import verify_portfolio_completion as portfolio


def trial(trial_id: str, **overrides):
    value = {
        "schema_version": 1,
        "trial_id": trial_id,
        "participant_scope": "trusted_tester",
        "consent_confirmed": True,
        "apple_silicon": True,
        "macos_major": 14,
        "app_version": "0.1.0",
        "artifact_sha256": "a" * 64,
        "unsigned_internal_build_acknowledged": True,
        "results": {name: "pass" for name in portfolio.REQUIRED_RESULTS},
        "support_friction": "No additional friction.",
        "qualitative_feedback": "The bounded flow was understandable.",
        "release_blockers": [],
        "sensitive_material_committed": False,
    }
    value.update(overrides)
    return value


class PortfolioCompletionTests(unittest.TestCase):
    def test_repository_demo_is_bounded_to_two_to_four_minutes(self):
        self.assertEqual(portfolio.demo_duration_seconds(), 210)

    def test_three_clean_trials_allow_internal_go_but_never_public_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            trials = base / "trials"
            trials.mkdir()
            demo = base / "demo.json"
            demo.write_text(json.dumps({
                "recorded": True,
                "production_app": True,
                "byok_hidden": True,
                "wake_and_acknowledgement": True,
                "normal_followup_tool_turns": True,
                "interruption": True,
                "semantic_end_and_media_release": True,
                "diagnostics_and_clean_quit": True,
                "duration_seconds": 210,
                "sensitive_material_visible": False,
                "public_binary_linked": False,
                "public_demo_reference": "https://example.invalid/demo",
            }))
            for index in range(3):
                (trials / f"trial-{index}.json").write_text(
                    json.dumps(trial(f"trial-{index}")), encoding="utf-8"
                )
            report = portfolio.completion_report(trials, demo)
            self.assertEqual(report["status"], "GO_INTERNAL")
            self.assertEqual(report["public_binary_distribution"], "HOLD")

    def test_missing_trials_or_any_blocker_holds_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "trial.json").write_text(
                json.dumps(trial("trial-one", results={
                    **{name: "pass" for name in portfolio.REQUIRED_RESULTS},
                    "cleanup": "fail",
                })),
                encoding="utf-8",
            )
            report = portfolio.completion_report(base, base / "missing-demo.json")
            self.assertEqual(report["status"], "HOLD")
            self.assertIn("trial-one:cleanup", report["blockers"])
            self.assertIn("demo:not_recorded", report["blockers"])

    def test_privacy_forbidden_fields_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trial.json"
            path.write_text(json.dumps(trial("trial-one", transcript="secret")))
            with self.assertRaisesRegex(portfolio.CompletionError, "privacy-forbidden"):
                portfolio.validate_trial(path)


if __name__ == "__main__":
    unittest.main()

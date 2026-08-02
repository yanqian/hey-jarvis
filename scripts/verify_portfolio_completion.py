#!/usr/bin/env python3
"""Validate privacy-safe F093 demo and trusted-trial completion evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "feedback" / "trusted-trials"
DEMO_PLAN = ROOT / "docs" / "PORTFOLIO_DEMO.md"
DEMO_EVIDENCE = ROOT / "feedback" / "demo-evidence.json"
MIN_TRIALS = 3
REQUIRED_RESULTS = (
    "install",
    "first_run",
    "wake",
    "conversation",
    "interruption",
    "cleanup",
    "relaunch",
)
FORBIDDEN_KEYS = {
    "api_key",
    "audio",
    "raw_audio",
    "transcript",
    "conversation_text",
    "serial_number",
    "email",
    "full_name",
}
BLOCKING_RESULTS = {"fail", "blocked"}


class CompletionError(ValueError):
    """Raised when completion evidence violates the F093 contract."""


def _objects(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def validate_trial(path: Path) -> dict[str, Any]:
    try:
        trial = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompletionError(f"{path.name}: invalid JSON: {exc}") from exc
    if not isinstance(trial, dict):
        raise CompletionError(f"{path.name}: root must be an object")

    for obj in _objects(trial):
        leaked = FORBIDDEN_KEYS.intersection(key.lower() for key in obj)
        if leaked:
            raise CompletionError(
                f"{path.name}: privacy-forbidden fields: {', '.join(sorted(leaked))}"
            )

    required = {
        "schema_version",
        "trial_id",
        "participant_scope",
        "consent_confirmed",
        "apple_silicon",
        "macos_major",
        "app_version",
        "artifact_sha256",
        "unsigned_internal_build_acknowledged",
        "results",
        "support_friction",
        "qualitative_feedback",
        "release_blockers",
        "sensitive_material_committed",
    }
    missing = required.difference(trial)
    if missing:
        raise CompletionError(f"{path.name}: missing fields: {', '.join(sorted(missing))}")
    if trial["schema_version"] != 1:
        raise CompletionError(f"{path.name}: unsupported schema_version")
    if trial["participant_scope"] not in {"trusted_tester", "clean_local_profile"}:
        raise CompletionError(f"{path.name}: participant_scope is not eligible")
    if trial["consent_confirmed"] is not True:
        raise CompletionError(f"{path.name}: consent is not confirmed")
    if trial["apple_silicon"] is not True or int(trial["macos_major"]) < 14:
        raise CompletionError(f"{path.name}: requires Apple Silicon and macOS 14+")
    if trial["unsigned_internal_build_acknowledged"] is not True:
        raise CompletionError(f"{path.name}: unsigned-build warning was not acknowledged")
    if trial["sensitive_material_committed"] is not False:
        raise CompletionError(f"{path.name}: sensitive material must not be committed")
    sha = trial["artifact_sha256"]
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise CompletionError(f"{path.name}: artifact_sha256 must be lowercase SHA-256")

    results = trial["results"]
    if not isinstance(results, dict):
        raise CompletionError(f"{path.name}: results must be an object")
    for result in REQUIRED_RESULTS:
        if results.get(result) not in {"pass", "fail", "blocked"}:
            raise CompletionError(f"{path.name}: invalid or missing result {result}")
    for field in ("support_friction", "qualitative_feedback"):
        value = trial[field]
        if not isinstance(value, str) or not value.strip():
            raise CompletionError(f"{path.name}: {field} must be a non-empty summary")
    if not isinstance(trial["release_blockers"], list):
        raise CompletionError(f"{path.name}: release_blockers must be a list")
    return trial


def demo_duration_seconds(path: Path = DEMO_PLAN) -> int:
    text = path.read_text(encoding="utf-8")
    marker = "DEMO_DURATION_SECONDS:"
    lines = [line for line in text.splitlines() if line.startswith(marker)]
    if len(lines) != 1:
        raise CompletionError("demo plan must contain exactly one duration marker")
    try:
        duration = int(lines[0].split(":", 1)[1].strip())
    except ValueError as exc:
        raise CompletionError("demo duration marker must be an integer") from exc
    if not 120 <= duration <= 240:
        raise CompletionError("demo duration must be between 120 and 240 seconds")
    return duration


def validate_demo_evidence(path: Path = DEMO_EVIDENCE) -> list[str]:
    if not path.exists():
        return ["demo:not_recorded"]
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompletionError(f"demo evidence is invalid JSON: {exc}") from exc
    required_true = (
        "recorded",
        "production_app",
        "byok_hidden",
        "wake_and_acknowledgement",
        "normal_followup_tool_turns",
        "interruption",
        "semantic_end_and_media_release",
        "diagnostics_and_clean_quit",
    )
    blockers = [f"demo:{key}" for key in required_true if evidence.get(key) is not True]
    duration = evidence.get("duration_seconds")
    if not isinstance(duration, int) or not 120 <= duration <= 240:
        blockers.append("demo:duration")
    if evidence.get("sensitive_material_visible") is not False:
        blockers.append("demo:sensitive_material")
    if evidence.get("public_binary_linked") is not False:
        blockers.append("demo:public_binary")
    reference = evidence.get("public_demo_reference")
    if not isinstance(reference, str) or not reference.strip():
        blockers.append("demo:missing_reference")
    return blockers


def completion_report(
    evidence_dir: Path = EVIDENCE_DIR,
    demo_evidence: Path = DEMO_EVIDENCE,
) -> dict[str, Any]:
    duration = demo_duration_seconds()
    trials = [validate_trial(path) for path in sorted(evidence_dir.glob("*.json"))]
    distinct = {trial["trial_id"] for trial in trials}
    if len(distinct) != len(trials):
        raise CompletionError("trial_id values must be unique")
    blockers = validate_demo_evidence(demo_evidence)
    for trial in trials:
        failed = [
            name for name in REQUIRED_RESULTS if trial["results"][name] in BLOCKING_RESULTS
        ]
        blockers.extend(f"{trial['trial_id']}:{name}" for name in failed)
        blockers.extend(f"{trial['trial_id']}:{item}" for item in trial["release_blockers"])
    return {
        "status": "GO_INTERNAL" if len(trials) >= MIN_TRIALS and not blockers else "HOLD",
        "public_binary_distribution": "HOLD",
        "demo_duration_seconds": duration,
        "completed_trials": len(trials),
        "required_trials": MIN_TRIALS,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        report = completion_report()
    except CompletionError as exc:
        print(json.dumps({"status": "HOLD", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    if args.require_complete and report["status"] != "GO_INTERNAL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

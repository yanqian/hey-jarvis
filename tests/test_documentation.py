import json
import re
import unittest
from pathlib import Path

from src.config import DEPENDENCY_MODULES
from src.main import build_parser


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ENV_EXAMPLE = ROOT / ".env.example"
DEPLOYMENT = ROOT / "DEPLOYMENT.md"
MANUAL_TESTING = ROOT / "MANUAL_TESTING.md"
CONFIGURATION = ROOT / "docs" / "CONFIGURATION.md"
PIPELINE = ROOT / "docs" / "PIPELINE.md"
REALTIME = ROOT / "docs" / "REALTIME.md"
TROUBLESHOOTING = ROOT / "docs" / "TROUBLESHOOTING.md"
PORTFOLIO_CASE_STUDY = ROOT / "docs" / "PORTFOLIO_CASE_STUDY.md"
PORTFOLIO_DEMO = ROOT / "docs" / "PORTFOLIO_DEMO.md"
PORTFOLIO_COMPLETION = ROOT / "docs" / "PORTFOLIO_COMPLETION.md"
TRUSTED_FEEDBACK = ROOT / "feedback" / "README.md"
PROGRESS = ROOT / ".agent-harness" / "progress.md"
FEATURE_LIST = ROOT / ".agent-harness" / "feature_list.json"

PROJECT_DOCS = (
    README,
    DEPLOYMENT,
    CONFIGURATION,
    PIPELINE,
    REALTIME,
    TROUBLESHOOTING,
    MANUAL_TESTING,
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class DocumentationTests(unittest.TestCase):
    def test_readme_is_a_concise_project_landing_page(self):
        readme = read(README)

        self.assertLessEqual(len(readme.splitlines()), 220)
        for heading in (
            "# Hey Jarvis",
            "## Requirements",
            "## Quick start",
            "## Useful commands",
            "## What it can do",
            "## Privacy and safety",
            "## Documentation",
            "## Recovery",
        ):
            self.assertIn(heading, readme)

        for phrase in (
            "Pipeline",
            "Realtime",
            "pipeline",
            "realtime",
            "python -m src.main",
            "python -m src.main --backend realtime",
            "Python 3.11 or Python 3.12",
            "macOS",
            "billable",
            "Pre-wake",
        ):
            self.assertIn(phrase, readme)

        self.assertNotIn("REALTIME_MODEL=", readme)
        self.assertNotIn("ARMED_SNR_MULTIPLIER=", readme)
        self.assertNotIn("RT004 version", readme)

    def test_readme_maps_user_and_developer_documents(self):
        readme = read(README)

        for target in (
            "DEPLOYMENT.md",
            "docs/CONFIGURATION.md",
            "docs/PIPELINE.md",
            "docs/REALTIME.md",
            "docs/TROUBLESHOOTING.md",
            "MANUAL_TESTING.md",
            "SPEC.md",
            "AGENTS.md",
            "docs/PORTFOLIO_CASE_STUDY.md",
            "docs/PORTFOLIO_DEMO.md",
            "docs/PORTFOLIO_COMPLETION.md",
            "feedback/README.md",
        ):
            self.assertIn(target, readme)

        self.assertIn("Developer references", readme)
        self.assertIn("Development history", readme)
        self.assertIn(".agent-harness/", readme)
        self.assertIn(".agent-harness/runs/", readme)
        self.assertNotIn("`.agent-harness/` and `runs/`", readme)

    def test_portfolio_material_is_honest_private_and_reproducible(self):
        case_study = read(PORTFOLIO_CASE_STUDY)
        normalized_case_study = " ".join(case_study.split())
        demo = read(PORTFOLIO_DEMO)
        feedback = read(TRUSTED_FEEDBACK)
        completion = read(PORTFOLIO_COMPLETION)
        normalized_completion = " ".join(completion.split())

        for phrase in (
            "four practical goals",
            "F086",
            "Rust/Tauri",
            "WKWebView",
            "Python 3.12 sidecar",
            "AI Agent Harness",
            "45,439,075 bytes",
            "83 nested Mach-O",
            "INTERNAL-UNSIGNED",
            "Public binary distribution stays on hold",
            "retained CLI",
        ):
            self.assertIn(phrase, normalized_case_study)
        for phrase in (
            "DEMO_DURATION_SECONDS: 210",
            "Check microphone & start",
            "Enable voice assistant",
            "follow-up",
            "Interrupt",
            "再见",
            "Export support bundle",
            "Quit from the tray",
        ):
            self.assertIn(phrase, demo)
        for phrase in (
            "at least three",
            "trial-template.json",
            "verify_portfolio_completion.py",
            "public binary distribution remains `HOLD`",
        ):
            self.assertIn(phrase, feedback)
        for phrase in (
            "Current decision: HOLD",
            "45,439,075 bytes",
            "83 arm64 Mach-O",
            "two more",
            "Public binary distribution",
            "Python CLI",
            "hosted control plane",
        ):
            self.assertIn(phrase, normalized_completion)

    def test_recovery_progress_matches_latest_documentation_state(self):
        progress = read(PROGRESS)
        last_completed = progress.split("## Last Completed Feature", 1)[1].split(
            "## Recent Completed Feature History", 1
        )[0]
        current_feature = progress.split("## Current Feature", 1)[1].split(
            "## Next Feature", 1
        )[0]
        normalized_current_feature = " ".join(current_feature.split())
        next_feature = progress.split("## Next Feature", 1)[1].split(
            "## Recently Completed", 1
        )[0]
        normalized_next_feature = " ".join(next_feature.split())
        recently_completed = progress.split("## Recently Completed", 1)[1].split(
            "## Known Issues", 1
        )[0]
        known_issues = progress.split("## Known Issues", 1)[1].split(
            "## Operational and Verification Constraints", 1
        )[0]

        self.assertIn("F097 - Polish Settings interaction and compact layout", last_completed)
        self.assertIn("EVAL_PASS: F097", last_completed)
        self.assertIn("standard `⌘,` shortcut", last_completed)
        self.assertNotIn(
            "F070 - Keep Realtime input-level diagnostics", last_completed
        )
        features = json.loads(read(FEATURE_LIST))["features"]
        f099 = next(feature for feature in features if feature["id"] == "F099")
        if f099["status"] == "in_progress":
            self.assertIn("F099 - Make Settings return lifecycle deterministic", current_feature)
            self.assertIn("requestAnimationFrame", normalized_current_feature)
            self.assertIn("BFCache", normalized_current_feature)
        elif f099["status"] == "done":
            self.assertIn("No feature is currently in progress", current_feature)
            self.assertIn("F099 is evaluator-approved", normalized_current_feature)
        self.assertIn("F093 is pending (`status=todo`)", current_feature)
        self.assertIn("internal artifact", current_feature)
        self.assertIn("machine-readable decision is `HOLD`", current_feature)
        self.assertIn("Resume F093", next_feature)
        self.assertIn("two additional trusted Apple Silicon", normalized_next_feature)
        self.assertIn("Public binary distribution remains on hold", next_feature)
        self.assertNotIn("No unfinished features remain", next_feature)
        self.assertIn("F077 - Measure acknowledgement playback lifecycle", recently_completed)
        self.assertIn("F094 - Create the minimal voice interaction surface", recently_completed)
        self.assertIn("F091 - Harden app diagnostics and sidecar recovery", recently_completed)
        self.assertNotIn("F065 - Make Realtime farewell closure", recently_completed)
        self.assertIn("F061", known_issues)
        self.assertIn("passed the synchronized RT003 run", known_issues)
        self.assertNotIn("Realtime wake-to-ready latency", known_issues)
        self.assertNotIn("after F060 evaluator review", known_issues)

        spec = (ROOT / ".agent-harness" / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn(
            "Feature mapping: this normalized parent requirement covers F082",
            spec,
        )
        self.assertIn("F083 (foreign exchange), and F084 (stock quotes)", spec)

    def test_mac_settings_documentation_matches_the_non_listening_surface(self):
        readme = read(README)
        manual = read(MANUAL_TESTING)
        internal = read(ROOT / "docs" / "INTERNAL_MAC_APP_TESTING.md")
        normalized_internal = " ".join(internal.split())
        diagnostics = read(ROOT / "docs" / "MAC_APP_DIAGNOSTICS.md")
        normalized_diagnostics = " ".join(diagnostics.split())

        for phrase in (
            "menu-bar icon",
            "`⌘,`",
            "Opening Settings stops voice listening",
            "Privacy & Diagnostics",
        ):
            self.assertIn(phrase, readme)
        self.assertIn("| M095 | Dedicated Settings presentation |", manual)
        self.assertIn(
            "General, API Keys, Microphone, Privacy & Diagnostics, and About",
            normalized_internal,
        )
        self.assertIn("standard `⌘,` shortcut", diagnostics)
        self.assertIn("intentionally stops the sidecar", normalized_diagnostics)

    def test_all_env_keys_are_owned_by_configuration_reference(self):
        configuration = read(CONFIGURATION)

        for line in read(ENV_EXAMPLE).splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0]
            self.assertIn(f"`{key}`", configuration)

        self.assertIn("never commit", configuration)
        self.assertIn(".env.example", configuration)

    def test_cli_modes_are_documented_outside_one_exhaustive_page(self):
        help_text = build_parser().format_help()
        combined = "\n".join(read(path) for path in PROJECT_DOCS)

        for flag in (
            "--dry-run",
            "--diagnose",
            "--fake-backend",
            "--prepare-wake-word",
            "--prepare-acknowledgement",
            "--benchmark-acknowledgement",
            "--benchmark-iterations",
            "--text",
            "--wake-debug",
            "--wake-file",
            "--wake-debug-output",
        ):
            self.assertIn(flag, help_text)
            self.assertIn(flag, combined)

        self.assertIn("python -m src.main", read(README))
        self.assertIn("python -m src.main", read(DEPLOYMENT))

    def test_deployment_owns_supported_install_verify_and_run_flow(self):
        deployment = read(DEPLOYMENT)

        for phrase in (
            "Python 3.11 or Python 3.12",
            "pip install -r requirements.txt",
            "OPENAI_API_KEY",
            "python -m src.main --prepare-wake-word",
            "python -m src.main --prepare-acknowledgement",
            "./init.sh",
            "python -m src.main --diagnose",
            "System Settings → Privacy & Security → Microphone",
            "python -m src.main --backend realtime",
            "once per launched Chrome host",
            "Review `.env.example`",
            "tmp/input.wav",
            "tmp/realtime-evals/",
        ):
            self.assertIn(phrase, deployment)

        self.assertIn("pipeline remains the default", deployment.lower())
        self.assertIn("billable", deployment.lower())
        self.assertIn("packaged application", deployment)

    def test_pipeline_guide_owns_routing_knowledge_language_and_timing(self):
        pipeline = read(PIPELINE)

        for phrase in (
            "WAIT_WAKE → ACK_PLAYING → ARMED → RECORDING",
            "Open-Meteo",
            "Frankfurter",
            "Finnhub",
            "never executed with `eval`",
            "does not browse the web",
            "must not claim that sources or current facts were checked",
            "Chinese input receives concise Simplified Chinese",
            "pipeline_timing",
            "response_timing",
            "ready_to_play",
            "monotonic elapsed durations",
            "python -m src.main --fake-backend",
        ):
            self.assertIn(phrase, pipeline)

    def test_realtime_guide_owns_operator_privacy_and_tool_boundaries(self):
        realtime = read(REALTIME)

        for phrase in (
            "pipeline remains the default",
            "once per Chrome host launch",
            "exactly six allowlisted local functions",
            "`calculator`",
            "`weather`",
            "`local_time`",
            "`fx`",
            "`stock`",
            "`end_conversation`",
            "`function_call_output`",
            "DEFAULT_LOCATION=Singapore",
            "Trading actions, shell access",
            "Pre-wake",
            "unified WebRTC call interface",
            "never an API credential",
            "billable",
            "bounded sanitized",
            "current audio turn",
            "Mandarin Chinese",
            "English receives English",
            "REALTIME_VOICE=alloy",
            "REALTIME_OUTPUT_VOLUME=0.5",
            "REALTIME_SERVER_VAD_THRESHOLD=0.8",
            "REALTIME_INPUT_NOISE_REDUCTION=far_field",
            "playback-buffer",
            "for exactly the next wake-triggered session",
        ):
            self.assertIn(phrase, realtime)

        for stale in ("WebSocket host", "conversation.item.truncate", "response.cancel"):
            self.assertNotIn(stale, realtime)

    def test_realtime_eval_contracts_are_in_realtime_guide(self):
        realtime = " ".join(read(REALTIME).split())

        for command in (
            "python -m src.evals.realtime_handoff live",
            "python -m src.evals.realtime_handoff offline",
            "python -m src.evals.realtime_two_turn live",
            "python -m src.evals.realtime_close_recovery live",
            "python -m src.evals.realtime_barge_in live",
            "python -m src.evals.realtime_input_diagnosis live",
        ):
            self.assertIn(command, realtime)

        for phrase in (
            "needs no fresh human speech",
            "Routine runs require no fresh speech",
            "connects session A",
            "distinct session B",
            "first-minus-second",
            "all six nested fields",
            "without being counted twice",
            "one fail-closed pre-session readiness gate",
            "no second terminal/chat round trip",
            "no_remote_playback",
            "remote_playback",
            "server_vad_sensitivity",
            "full_duplex_attenuation",
            "not automatic tuning and not an RT003 pass",
            "strict diagnostic allowlist",
            "`error.type` and `error.code`",
            "never retains the full provider response body",
        ):
            self.assertIn(phrase, realtime)

    def test_troubleshooting_owns_common_recovery_and_wake_debug(self):
        troubleshooting = read(TROUBLESHOOTING)

        for phrase in (
            "OPENAI_API_KEY is required",
            "requirements-vad.txt",
            "ai-edge-litert",
            "wake_acknowledgement_audio",
            "var/ack.mp3",
            "WAKE_INFERENCE_FRAMEWORK=tflite",
            "python -m src.main --wake-debug",
            "--wake-debug-output",
            "python -m src.main --wake-file",
            "rms",
            "peak",
            "overflow=true",
            "audio processing may have fallen behind",
            "WAKE_THRESHOLD",
            "WAIT_WAKE",
            "armed_summary",
            "armed_trigger",
            "baseline_ready=true",
            "noise_floor_has_samples=true",
            "afplay",
            "FINNHUB_API_KEY",
        ):
            self.assertIn(phrase, troubleshooting)

    def test_runtime_dependencies_and_optional_vad_contract_are_documented(self):
        combined = "\n".join(read(path) for path in PROJECT_DOCS)

        for module in DEPENDENCY_MODULES:
            self.assertIn(module, combined)

        optional_requirements = read(ROOT / "requirements-vad.txt")
        self.assertIn("webrtcvad==2.0.10", optional_requirements)
        self.assertIn("setuptools<81", optional_requirements)
        self.assertIn("VAD_BACKEND", read(CONFIGURATION))
        self.assertIn("disabled by default", read(CONFIGURATION))

    def test_manual_acceptance_catalog_remains_reachable_and_intact(self):
        manual = read(MANUAL_TESTING)

        for marker in (
            "M023",
            "M028",
            "M030",
            "M031",
            "M032",
            "M047",
            "M057",
            "M058",
            "M060",
            "M062",
            "M063",
            "M064",
            "M065",
            "M066",
        ):
            self.assertIn(marker, manual)

        self.assertIn("MANUAL_TESTING.md", read(README))
        self.assertIn("MANUAL_TESTING.md", read(DEPLOYMENT))

    def test_post_mvp_boundaries_are_still_explicit(self):
        readme = read(README)
        realtime = read(REALTIME)

        for phrase in (
            "signing",
            "notarization",
            "launch-at-login",
            "automatic updates",
            "distributable `.app`",
        ):
            self.assertIn(phrase, readme)

        self.assertIn("Trading actions, shell access", realtime)
        self.assertIn("`fx`", realtime)
        self.assertIn("`stock`", realtime)
        self.assertIn("weather", realtime)
        self.assertIn("outside the Realtime tool boundary", realtime)

    def test_unsigned_internal_distribution_is_explicit_and_bounded(self):
        guide = read(ROOT / "docs" / "INTERNAL_MAC_APP_TESTING.md")
        deployment = read(DEPLOYMENT)
        build = read(ROOT / "scripts" / "build_internal_macos_release.sh")

        for phrase in (
            "INTERNAL-UNSIGNED",
            "Open Anyway",
            "Do not disable Gatekeeper",
            "Do not put this DMG on a public download page",
            "manual install/update/rollback",
            "Developer ID signing and notarization",
        ):
            self.assertIn(phrase, guide)
        self.assertIn("INTERNAL-UNSIGNED", deployment)
        self.assertIn("Hey-Jarvis-$VERSION-INTERNAL-UNSIGNED-arm64", build)
        self.assertNotIn("notarytool", build)
        self.assertNotIn("stapler", build)
        self.assertNotIn("xattr", build)

    def test_local_markdown_links_resolve(self):
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

        for document in PROJECT_DOCS:
            for target in link_pattern.findall(read(document)):
                if (
                    target.startswith(("http://", "https://", "#", "mailto:"))
                    or "://" in target
                ):
                    continue
                path_text = target.split("#", 1)[0]
                if not path_text:
                    continue
                resolved = (document.parent / path_text).resolve()
                self.assertTrue(
                    resolved.exists(),
                    f"{document.relative_to(ROOT)} links to missing {target}",
                )


if __name__ == "__main__":
    unittest.main()

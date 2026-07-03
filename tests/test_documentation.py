import unittest
from pathlib import Path

from src.config import DEPENDENCY_MODULES
from src.main import build_parser


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ENV_EXAMPLE = ROOT / ".env.example"


class DocumentationTests(unittest.TestCase):
    def test_readme_documents_cli_modes_from_parser(self):
        readme = README.read_text(encoding="utf-8")
        help_text = build_parser().format_help()

        for flag in (
            "--dry-run",
            "--diagnose",
            "--fake-backend",
            "--prepare-wake-word",
            "--wake-debug",
            "--wake-file",
        ):
            self.assertIn(flag, help_text)
            self.assertIn(f"python -m src.main {flag}", readme)

        self.assertIn("python -m src.main", readme)

    def test_readme_documents_env_example_keys(self):
        readme = README.read_text(encoding="utf-8")
        env_text = ENV_EXAMPLE.read_text(encoding="utf-8")

        for line in env_text.splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0]
            self.assertIn(key, readme)

    def test_readme_documents_runtime_requirements_and_mvp_followups(self):
        readme = README.read_text(encoding="utf-8")

        self.assertIn("Python 3.11 or Python 3.12", readme)
        self.assertIn("macOS microphone permission", readme)
        self.assertIn("Microphone input overflows", readme)
        self.assertIn("Wake-Word Debugging", readme)
        self.assertIn("--wake-debug-output", readme)
        self.assertIn("tmp/input.wav", readme)
        self.assertIn("frame count", readme)
        self.assertIn("maximum observed score", readme)
        self.assertIn("rms", readme)
        self.assertIn("peak", readme)
        self.assertIn("score", readme)
        self.assertIn("threshold", readme)
        self.assertIn("WAIT_WAKE", readme)
        self.assertIn("audio processing may have fallen behind", readme)
        self.assertIn("afplay", readme)
        self.assertIn("Hey Jarvis", readme)
        self.assertIn("what is two plus two?", readme)
        self.assertIn("Interrupt playback", readme)
        self.assertIn("six-second follow-up", readme)
        self.assertIn("custom wake-word model loading", readme)

        for package_name in DEPENDENCY_MODULES:
            self.assertIn(package_name, readme)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from src.config import DEPENDENCY_MODULES
from src.main import build_parser


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ENV_EXAMPLE = ROOT / ".env.example"
DEPLOYMENT = ROOT / "DEPLOYMENT.md"
MANUAL_TESTING = ROOT / "MANUAL_TESTING.md"


class DocumentationTests(unittest.TestCase):
    def test_readme_documents_cli_modes_from_parser(self):
        readme = README.read_text(encoding="utf-8")
        deployment = DEPLOYMENT.read_text(encoding="utf-8")
        help_text = build_parser().format_help()

        for flag in (
            "--dry-run",
            "--diagnose",
            "--fake-backend",
            "--prepare-wake-word",
            "--prepare-acknowledgement",
            "--text",
            "--wake-debug",
            "--wake-file",
        ):
            self.assertIn(flag, help_text)
            self.assertIn(f"python -m src.main {flag}", readme)
            self.assertIn(f"python -m src.main {flag}", deployment)

        self.assertIn("python -m src.main", readme)
        self.assertIn("python -m src.main", deployment)

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
        deployment = DEPLOYMENT.read_text(encoding="utf-8")
        manual_testing = MANUAL_TESTING.read_text(encoding="utf-8")

        self.assertIn("Python 3.11 or Python 3.12", readme)
        self.assertIn("Python 3.11 or Python 3.12", deployment)
        self.assertIn("macOS microphone permission", readme)
        self.assertIn("macOS with microphone access", deployment)
        self.assertIn("Microphone input overflows", readme)
        self.assertIn("Wake-Word Debugging", readme)
        self.assertIn("--wake-debug-output", readme)
        self.assertIn("--wake-debug-output", deployment)
        self.assertIn("tmp/input.wav", readme)
        self.assertIn("tmp/input.wav", deployment)
        self.assertIn("frame count", readme)
        self.assertIn("maximum observed score", readme)
        self.assertIn("rms", readme)
        self.assertIn("rms", deployment)
        self.assertIn("peak", readme)
        self.assertIn("peak", deployment)
        self.assertIn("score", readme)
        self.assertIn("wake scores", deployment)
        self.assertIn("threshold", readme)
        self.assertIn("WAKE_THRESHOLD", deployment)
        self.assertIn("WAIT_WAKE", readme)
        self.assertIn("WAIT_WAKE", deployment)
        self.assertIn("audio processing may have fallen behind", readme)
        self.assertIn("afplay", readme)
        self.assertIn("afplay", deployment)
        self.assertIn("Hey Jarvis", readme)
        self.assertIn("Hey Jarvis", deployment)
        self.assertIn("openWakeWord", readme)
        self.assertIn("openWakeWord", deployment)
        self.assertIn("ai-edge-litert", readme)
        self.assertIn("ai-edge-litert", deployment)
        self.assertIn("WAKE_BACKEND=openwakeword", readme)
        self.assertIn("WAKE_BACKEND=openwakeword", deployment)
        self.assertIn("WAKE_MODEL=hey_jarvis", readme)
        self.assertIn("WAKE_MODEL=hey_jarvis", deployment)
        self.assertIn("WAKE_INFERENCE_FRAMEWORK=tflite", readme)
        self.assertIn("WAKE_INFERENCE_FRAMEWORK=tflite", deployment)
        self.assertIn("scripts/debug_oww_file.py", readme)
        self.assertIn("wake_word_models", readme)
        self.assertIn("wake_word_models", deployment)
        self.assertIn("WAKE_THRESHOLD=0.5", readme)
        self.assertIn("WAKE_THRESHOLD=0.5", deployment)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_ENABLED=1", readme)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_ENABLED=1", deployment)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_TEXT=在呢", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("WAKE_ACKNOWLEDGEMENT_AUDIO_PATH=tmp/ack.mp3", readme)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS=0.35", deployment)
        self.assertIn("wake_acknowledgement_audio", readme)
        self.assertIn("wake_acknowledgement_audio", deployment)
        self.assertIn("tmp/ack.mp3", deployment)
        self.assertIn("M023", manual_testing)
        self.assertIn("WAKE_PHRASE=hey jarvis", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("WAKE_MODEL=hey_jarvis", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("WAKE_INFERENCE_FRAMEWORK=tflite", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("what is two plus two?", readme)
        self.assertIn("what is two plus two?", deployment)
        self.assertIn("MANUAL_TESTING.md", readme)
        self.assertIn("MANUAL_TESTING.md", deployment)
        self.assertIn("SILENCE_SECONDS", manual_testing)
        self.assertIn("MAX_RECORD_SECONDS", manual_testing)
        self.assertIn("stopped_by=silence", manual_testing)
        self.assertIn("10-15 second question", manual_testing)
        self.assertIn("tmp/input.wav", manual_testing)
        self.assertIn("TTS_INSTRUCTIONS", readme)
        self.assertIn("TTS_INSTRUCTIONS", deployment)
        self.assertIn("TTS_SPEED=1.0", readme)
        self.assertIn("TTS_SPEED=1.0", deployment)
        self.assertIn("ENABLE_TOOLS=1", readme)
        self.assertIn("ENABLE_TOOLS=1", deployment)
        self.assertIn("TOOL_ROUTER_DEBUG=0", readme)
        self.assertIn("TOOL_ROUTER_DEBUG=0", deployment)
        self.assertIn("WEATHER_PROVIDER=open-meteo", readme)
        self.assertIn("WEATHER_PROVIDER=open-meteo", deployment)
        self.assertIn("FX_PROVIDER=frankfurter", readme)
        self.assertIn("FX_PROVIDER=frankfurter", deployment)
        self.assertIn("STOCK_PROVIDER=finnhub", readme)
        self.assertIn("STOCK_PROVIDER=finnhub", deployment)
        self.assertIn("TOOL_HTTP_TIMEOUT_SECONDS=5", readme)
        self.assertIn("TOOL_HTTP_TIMEOUT_SECONDS=5", deployment)
        self.assertIn("DEFAULT_LOCATION=Singapore", readme)
        self.assertIn("DEFAULT_LOCATION=Singapore", deployment)
        self.assertIn("DEFAULT_BASE_CURRENCY=USD", readme)
        self.assertIn("DEFAULT_BASE_CURRENCY=USD", deployment)
        self.assertIn("FINNHUB_API_KEY", readme)
        self.assertIn("FINNHUB_API_KEY", deployment)
        self.assertIn("Structured Tool Routing", readme)
        self.assertIn("provider-not-configured", readme)
        self.assertIn("mock the shared JSON HTTP boundary", deployment)
        self.assertIn("live provider network calls", readme)
        self.assertIn("python -m src.main --text", readme)
        self.assertIn("python -m src.main --text", deployment)
        self.assertIn("今天有什么新闻", readme)
        self.assertIn("今天有什么新闻", deployment)
        self.assertIn("OpenAI.fm-style vibe", readme)
        self.assertIn("OpenAI.fm-style vibe", deployment)
        self.assertIn("Interrupt playback", readme)
        self.assertIn("six-second follow-up", readme)
        self.assertIn("custom wake-word model loading", readme)

        for package_name in DEPENDENCY_MODULES:
            self.assertIn(package_name, readme)


if __name__ == "__main__":
    unittest.main()

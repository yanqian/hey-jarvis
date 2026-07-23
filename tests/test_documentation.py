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
    def test_rt001_documents_automatic_no_speech_handoff_boundary(self):
        readme = README.read_text(encoding="utf-8")
        manual_testing = MANUAL_TESTING.read_text(encoding="utf-8")
        readme_words = " ".join(readme.split())

        self.assertIn("python -m src.evals.realtime_handoff live", readme)
        self.assertIn("needs no fresh human speech", readme)
        self.assertIn("requires explicit authorization", readme_words)
        self.assertIn("python -m src.evals.realtime_handoff offline", readme)
        self.assertIn("M062", manual_testing)
        self.assertIn("Do not speak", manual_testing)
        self.assertIn("No user question or assistant answer is part of RT001", manual_testing)

    def test_rt002_documents_one_time_fixture_setup_and_automatic_replay(self):
        readme = README.read_text(encoding="utf-8")
        manual_testing = MANUAL_TESTING.read_text(encoding="utf-8")
        self.assertIn("python -m src.evals.realtime_two_turn live", readme)
        self.assertIn("require no fresh speech", readme)
        self.assertIn("not transcript or answer semantics", readme)
        self.assertIn("after browser echo cancellation", readme)
        self.assertIn("M063", manual_testing)
        self.assertIn("without speaking", manual_testing)
        self.assertIn("after browser AEC", manual_testing)

    def test_rt004_documents_automatic_two_session_cleanup(self):
        readme = README.read_text(encoding="utf-8")
        manual_testing = MANUAL_TESTING.read_text(encoding="utf-8")
        self.assertIn("python -m src.evals.realtime_close_recovery live", readme)
        self.assertIn("Routine RT004 runs require no fresh speech", readme)
        self.assertIn("connects session A", readme)
        self.assertIn("distinct session B", readme)
        self.assertIn("M064", manual_testing)
        self.assertIn("without another Arm action", manual_testing)

    def test_rt003_documents_one_pre_session_gate_and_in_band_confirmation(self):
        readme = README.read_text(encoding="utf-8")
        manual_testing = MANUAL_TESTING.read_text(encoding="utf-8")
        readme_words = " ".join(readme.split())
        manual_words = " ".join(manual_testing.split())

        self.assertIn("one fail-closed pre-session readiness gate", readme)
        self.assertIn("no second terminal/chat round trip", readme_words)
        self.assertNotIn("two fail-closed operator gates", readme)
        self.assertIn("That utterance doubles as audible confirmation", manual_words)
        self.assertIn("no second terminal/chat round trip", manual_words)

    def test_realtime_input_level_diagnosis_is_documented_without_tuning_claims(self):
        readme = README.read_text(encoding="utf-8")
        manual_testing = MANUAL_TESTING.read_text(encoding="utf-8")

        self.assertIn("python -m src.evals.realtime_input_diagnosis live", readme)
        self.assertIn("no_remote_playback", readme)
        self.assertIn("remote_playback", readme)
        self.assertIn("server_vad_sensitivity", readme)
        self.assertIn("full_duplex_attenuation", readme)
        self.assertIn("not automatic tuning and not an RT003 pass", readme)
        self.assertIn("does not change `REALTIME_SERVER_VAD_THRESHOLD`", readme)
        self.assertIn("strict diagnostic allowlist", readme)
        self.assertIn("`error.type` and `error.code`", readme)
        self.assertIn("never retains the full provider response body", readme)
        self.assertIn("M060", manual_testing)
        self.assertIn("does not retain audio/transcripts", manual_testing)

    def test_pipeline_timing_and_language_policy_are_documented(self):
        readme = README.read_text(encoding="utf-8")
        manual_testing = MANUAL_TESTING.read_text(encoding="utf-8")

        self.assertIn("Response language and latency diagnostics", readme)
        self.assertIn("response_timing", readme)
        self.assertIn("ready_to_play", readme)
        self.assertIn("monotonic elapsed durations", readme)
        self.assertIn("do not log assistant answer text", readme)
        self.assertIn("M058", manual_testing)
        self.assertIn("中国为什么参与朝鲜战争", manual_testing)
        self.assertIn("人脸识别的英文怎么读", manual_testing)
        self.assertIn("Why did China enter the Korean War?", manual_testing)

    def test_realtime_mvp_operator_boundary_is_consistent(self):
        documents = [
            README.read_text(encoding="utf-8"),
            DEPLOYMENT.read_text(encoding="utf-8"),
            MANUAL_TESTING.read_text(encoding="utf-8"),
            ENV_EXAMPLE.read_text(encoding="utf-8"),
        ]
        combined = "\n".join(documents)
        for phrase in (
            "pipeline remains the default",
            "once per",
            "pre-wake",
            "billable",
            "calculator",
            "packaging",
            "bounded",
        ):
            self.assertIn(phrase.lower(), combined.lower())
        for stale in ("WebSocket host", "conversation.item.truncate", "response.cancel"):
            self.assertNotIn(stale, combined)
        self.assertIn("REALTIME_SERVER_VAD_THRESHOLD=0.8", combined)

    def test_realtime_calculator_only_boundary_is_documented(self):
        readme = README.read_text(encoding="utf-8")
        self.assertIn("exactly one local function: `calculator`", readme)
        self.assertIn("same existing `safe_calculator`", readme)
        self.assertIn("`function_call_output`", readme)
        self.assertIn("official Realtime function-calling flow", readme)
        self.assertIn("Weather, FX, stocks", readme)
        self.assertIn("never executed with `eval`", readme)

    def test_stable_knowledge_policy_and_manual_boundary_are_documented(self):
        readme = README.read_text(encoding="utf-8")
        manual_testing = MANUAL_TESTING.read_text(encoding="utf-8")

        self.assertIn("Stable Knowledge Answers", readme)
        self.assertIn("中国古代人的语言交流跟现在中国哪个省份的方言类似", readme)
        self.assertIn("does not browse the web", readme)
        self.assertIn("must not claim that sources or current facts were checked", readme)
        self.assertIn("今天有什么新闻", readme)
        self.assertIn("M047", manual_testing)
        self.assertIn("Stable knowledge versus realtime boundary", manual_testing)
        self.assertIn("does not claim it browsed or checked sources", manual_testing)

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
        self.assertIn("WAKE_ACKNOWLEDGEMENT_AUDIO_PATH=var/ack.mp3", readme)
        self.assertIn("WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS=0.35", deployment)
        self.assertIn("ACK_GUARD_ENABLED=1", readme)
        self.assertNotIn("ACK_GUARD_SECONDS", readme)
        self.assertIn("ACK_GUARD_MIN_QUIET_SECONDS=0.16", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("ACK_GUARD_QUIET_RMS=900", readme)
        self.assertIn("ACK_GUARD_MAX_BUFFER_SECONDS=1.50", readme)
        self.assertIn("ARMED_NO_SPEECH_TIMEOUT_SECONDS=2.0", readme)
        self.assertIn("ARMED_NO_SPEECH_TIMEOUT_SECONDS=2.0", deployment)
        self.assertIn("ARMED_VOICE_RMS=750", readme)
        self.assertIn("ARMED_MIN_RMS=750", readme)
        self.assertIn("ARMED_SNR_MULTIPLIER=2.5", readme)
        self.assertIn("ARMED_VOICE_WINDOW_SECONDS=0.30", readme)
        self.assertIn("ARMED_VOICE_REQUIRED_RATIO=0.75", readme)
        self.assertIn("ARMED_CLIP_REJECT_PEAK=32000", readme)
        self.assertIn("ARMED_PRE_ROLL_SECONDS=0.50", readme)
        self.assertIn("ARMED_BASELINE_SECONDS=0.30", readme)
        self.assertIn("ARMED_BASELINE_MIN_CHUNKS=3", readme)
        self.assertIn("ARMED_REQUIRE_BASELINE=1", readme)
        self.assertIn("ARMED_LAST_CHUNK_MUST_BE_VOICED=1", readme)
        self.assertIn("baseline_ready=true", readme)
        self.assertIn("VAD_BACKEND=disabled", readme)
        self.assertIn("VAD_MODE=2", readme)
        self.assertIn("WAKE_VAD_THRESHOLD=", readme)
        self.assertIn("ARMED_VAD_REQUIRED_RATIO=0.50", readme)
        self.assertIn("ARMED_VAD_MIN_FRAMES=2", readme)
        self.assertIn("RECORDING_VAD_ENABLED=0", readme)
        self.assertIn("RECORDING_VAD_END_RATIO=0.25", readme)
        self.assertIn("RECORDING_VAD_SPEECH_RATIO=0.50", readme)
        self.assertIn("RECORDING_HANGOVER_SECONDS=0.30", readme)
        self.assertIn("RECORDING_END_SILENCE_SECONDS=1.5", readme)
        self.assertIn("python -m pip install -r requirements-vad.txt", readme)
        optional_requirements = (ROOT / "requirements-vad.txt").read_text(encoding="utf-8")
        self.assertIn("webrtcvad==2.0.10", optional_requirements)
        self.assertIn("setuptools<81", optional_requirements)
        self.assertIn("post_ack_quiet_observed=false", readme)
        self.assertIn("noise_floor_has_samples=true", readme)
        self.assertIn("lower playback volume", readme)
        self.assertIn("clipped PCM is retained", readme)
        self.assertIn("neither erases earlier", readme)
        self.assertIn("armed_summary", readme)
        self.assertIn("armed_trigger", readme)
        self.assertIn("MIN_VALID_SPEECH_SECONDS=0.50", readme)
        self.assertIn("MIN_TRANSCRIPT_LENGTH=2", readme)
        self.assertIn("CANCEL_PHRASES=取消,没事,不用了,算了,stop,cancel,never mind", readme)
        self.assertIn("CANCEL_PHRASES=取消,没事,不用了,算了,stop,cancel,never mind", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("wake_acknowledgement_audio", readme)
        self.assertIn("wake_acknowledgement_audio", deployment)
        self.assertIn("var/ack.mp3", deployment)
        self.assertIn("M023", manual_testing)
        self.assertIn("M028", manual_testing)
        self.assertIn("M030", manual_testing)
        self.assertIn("M031", manual_testing)
        self.assertIn("M032", manual_testing)
        self.assertIn("没事不用了", readme)
        self.assertIn("不用不用了", readme)
        self.assertIn("不要了", deployment)
        self.assertIn("没事没事儿", manual_testing)
        self.assertIn("没事 后面有声音", readme)
        self.assertIn("没事不用了", deployment)
        self.assertIn("没事不用了", manual_testing)
        self.assertIn("不用了帮我查天气", readme)
        self.assertIn("没事的话帮我查天气", readme)
        self.assertIn("取消我明天的闹钟", deployment)
        self.assertIn("不要取消我明天的闹钟", deployment)
        self.assertIn("match_decision=not_cancelled", manual_testing)
        self.assertIn("match_mode=noisy_suffix", manual_testing)
        self.assertIn("no_speech_after_wake", manual_testing)
        self.assertIn("post-cancellation suppression", manual_testing)
        self.assertIn("post-cancellation wake", readme.lower())
        self.assertIn("maximum suppressed wake score", deployment)
        self.assertIn("WAKE_PHRASE=hey jarvis", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("WAKE_MODEL=hey_jarvis", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("WAKE_INFERENCE_FRAMEWORK=tflite", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("what is two plus two?", readme)
        self.assertIn("what is two plus two?", deployment)
        self.assertIn("MANUAL_TESTING.md", readme)
        self.assertIn("MANUAL_TESTING.md", deployment)
        self.assertIn("SILENCE_SECONDS", manual_testing)
        self.assertIn("MAX_RECORD_SECONDS", manual_testing)
        self.assertIn("RECORDING_SILENCE_RMS=750", readme)
        self.assertIn("RECORDING_SILENCE_RMS=750", ENV_EXAMPLE.read_text(encoding="utf-8"))
        self.assertIn("RECORDING_SILENCE_RMS", deployment)
        self.assertIn("RECORDING_SILENCE_RMS", manual_testing)
        self.assertIn("recent-window", manual_testing)
        self.assertIn("stopped_by=silence", manual_testing)
        self.assertIn("F048 passed 5/5 normal continuous", readme)
        self.assertIn("default enablement is a separate product decision", readme)
        self.assertIn("unresolved ARMED case", manual_testing)
        self.assertIn("after the prefix has left", manual_testing)
        self.assertIn("| M048 | Recording VAD false-high endpoint |", manual_testing)
        self.assertEqual(manual_testing.count("| M012 |"), 1)
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
        self.assertIn("TOOL_ANSWER_NATURALIZATION=1", readme)
        self.assertIn("TOOL_ANSWER_NATURALIZATION=1", deployment)
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
        self.assertIn("Open-Meteo", readme)
        self.assertIn("Open-Meteo", deployment)
        self.assertIn("Frankfurter", readme)
        self.assertIn("Frankfurter", deployment)
        self.assertIn("Finnhub", readme)
        self.assertIn("Finnhub", deployment)
        self.assertIn("market data may be delayed", readme)
        self.assertIn("not trading advice", deployment)
        self.assertIn("reference rate", readme)
        self.assertIn("bank cash rate", readme)
        self.assertIn("executable trade quote", readme)
        self.assertIn("Open-Meteo weather", manual_testing)
        self.assertIn("Frankfurter FX", manual_testing)
        self.assertIn("Finnhub stock quote", manual_testing)
        self.assertIn("Tool answer naturalization", manual_testing)
        self.assertIn("raw_answer", readme)
        self.assertIn("naturalization_status", deployment)
        self.assertIn("not_run_text_debug", manual_testing)
        self.assertIn("preserve numbers", readme)
        self.assertIn("advice disclaimers", deployment)
        self.assertIn("明天天气怎么样", readme)
        self.assertIn("明天天气怎么样", deployment)
        self.assertIn("weather in Tokyo today", readme)
        self.assertIn("weather in Tokyo today", deployment)
        self.assertIn("100 USD to SGD", readme)
        self.assertIn("100 USD to SGD", deployment)
        self.assertIn("100美元兑人民币汇率是多少", readme)
        self.assertIn("100美元兑人民币汇率是多少", deployment)
        self.assertIn("AAPL stock price", readme)
        self.assertIn("AAPL stock price", deployment)
        self.assertIn("苹果股价多少", readme)
        self.assertIn("苹果股价多少", deployment)
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
        self.assertIn("REALTIME_END_PHRASES", readme)
        self.assertIn("rough guide", readme)
        self.assertIn("ASR model", readme)
        self.assertIn("never transcript text", readme)
        self.assertIn("conversation.item.input_audio_transcription.completed", readme)

        for package_name in DEPENDENCY_MODULES:
            self.assertIn(package_name, readme)


if __name__ == "__main__":
    unittest.main()

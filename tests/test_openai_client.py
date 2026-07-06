import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace

from src.config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_RECORD_SECONDS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SILENCE_SECONDS,
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TTS_INSTRUCTIONS,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_SPEED,
    DEFAULT_TTS_VOICE,
    DEFAULT_WAKE_BACKEND,
    DEFAULT_WAKE_INFERENCE_FRAMEWORK,
    DEFAULT_WAKE_MODEL,
    DEFAULT_WAKE_PHRASE,
    DEFAULT_WAKE_THRESHOLD,
    Settings,
)
from src.openai_client import OpenAIClient, OpenAIClientError


def make_settings(openai_api_key="sk-test"):
    return Settings(
        openai_api_key=openai_api_key,
        wake_backend=DEFAULT_WAKE_BACKEND,
        wake_model=DEFAULT_WAKE_MODEL,
        wake_inference_framework=DEFAULT_WAKE_INFERENCE_FRAMEWORK,
        wake_phrase=DEFAULT_WAKE_PHRASE,
        wake_threshold=DEFAULT_WAKE_THRESHOLD,
        silence_seconds=DEFAULT_SILENCE_SECONDS,
        max_record_seconds=DEFAULT_MAX_RECORD_SECONDS,
        sample_rate=DEFAULT_SAMPLE_RATE,
        transcribe_model=DEFAULT_TRANSCRIBE_MODEL,
        chat_model=DEFAULT_CHAT_MODEL,
        tts_model=DEFAULT_TTS_MODEL,
        tts_voice=DEFAULT_TTS_VOICE,
        tts_instructions=DEFAULT_TTS_INSTRUCTIONS,
        tts_speed=DEFAULT_TTS_SPEED,
    )


class FakeTranscriptions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        kwargs["file"].read()
        return self.response


class FakeChatCompletions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeSpeechResponse:
    def __init__(self, data=b"mp3-data"):
        self.data = data
        self.streamed_to = None

    def stream_to_file(self, destination):
        self.streamed_to = Path(destination)
        self.streamed_to.write_bytes(self.data)


class FakeSpeechContext:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, exc_type, exc, traceback):
        return None


class FakeStreamingSpeech:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeSpeechContext(self.response)


class FakeSDKClient:
    def __init__(
        self,
        *,
        transcription_response=None,
        chat_response=None,
        speech_response=None,
    ):
        self.audio = SimpleNamespace(
            transcriptions=FakeTranscriptions(transcription_response or SimpleNamespace(text="hello jarvis")),
            speech=SimpleNamespace(
                with_streaming_response=FakeStreamingSpeech(speech_response or FakeSpeechResponse())
            ),
        )
        self.chat = SimpleNamespace(
            completions=FakeChatCompletions(
                chat_response
                or SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="Two plus two is four."))]
                )
            )
        )


class OpenAIClientTests(unittest.TestCase):
    def test_transcribe_audio_uses_configured_model_and_returns_text(self):
        fake_sdk = FakeSDKClient(transcription_response={"text": "  hello world  "})

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "input.wav"
            audio_path.write_bytes(b"wav-data")

            result = OpenAIClient(make_settings(), sdk_client=fake_sdk).transcribe_audio(str(audio_path))

        self.assertEqual(result, "hello world")
        call = fake_sdk.audio.transcriptions.calls[0]
        self.assertEqual(call["model"], DEFAULT_TRANSCRIBE_MODEL)
        self.assertEqual(Path(call["file"].name).name, "input.wav")

    def test_transcribe_audio_rejects_empty_transcription(self):
        fake_sdk = FakeSDKClient(transcription_response=SimpleNamespace(text="   "))

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "input.wav"
            audio_path.write_bytes(b"wav-data")

            with self.assertRaises(OpenAIClientError) as caught:
                OpenAIClient(make_settings(), sdk_client=fake_sdk).transcribe_audio(str(audio_path))

        self.assertIn("empty text", str(caught.exception))

    def test_ask_chatgpt_sends_history_and_updates_bounded_memory(self):
        fake_sdk = FakeSDKClient()
        history = [
            {"role": "user", "content": "old one"},
            {"role": "assistant", "content": "old two"},
            {"role": "user", "content": "recent question"},
        ]

        result = OpenAIClient(make_settings(), sdk_client=fake_sdk, history_limit=4).ask_chatgpt(
            "what is two plus two?",
            history,
        )

        self.assertEqual(result, "Two plus two is four.")
        call = fake_sdk.chat.completions.calls[0]
        self.assertEqual(call["model"], DEFAULT_CHAT_MODEL)
        self.assertEqual(call["messages"][0]["role"], "system")
        self.assertEqual(call["messages"][-1], {"role": "user", "content": "what is two plus two?"})
        self.assertEqual(history[0], {"role": "assistant", "content": "old two"})
        self.assertEqual(history[-1], {"role": "assistant", "content": "Two plus two is four."})
        self.assertEqual(len(history), 4)

    def test_ask_chatgpt_surfaces_api_failures(self):
        class FailingCompletions:
            def create(self, **kwargs):
                raise RuntimeError("network down")

        fake_sdk = FakeSDKClient()
        fake_sdk.chat.completions = FailingCompletions()

        with self.assertRaises(OpenAIClientError) as caught:
            OpenAIClient(make_settings(), sdk_client=fake_sdk).ask_chatgpt("hello", [])

        self.assertIn("OpenAI chat request failed", str(caught.exception))

    def test_naturalize_tool_answer_sends_authoritative_payload_without_history(self):
        fake_sdk = FakeSDKClient(
            chat_response=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Tomorrow in Singapore looks rainy, around 24 to 31 C, from Open-Meteo."
                        )
                    )
                ]
            )
        )
        history = [{"role": "user", "content": "old chat"}]

        result = OpenAIClient(make_settings(), sdk_client=fake_sdk).naturalize_tool_answer(
            question="明天天气怎么样",
            route={"category": "weather", "tool_name": "weather_provider", "intent": "tomorrow"},
            raw_answer="Tomorrow in Singapore, Singapore: 24.0 C to 31.0 C. Source: Open-Meteo.",
            summary="Open-Meteo forecast for 2026-07-07",
            data={
                "source": "Open-Meteo",
                "temperature_min_c": 24.0,
                "temperature_max_c": 31.0,
                "finnhub_api_key": "fh-secret",
                "token": "secret-token",
            },
        )

        self.assertIn("Open-Meteo", result)
        self.assertEqual(history, [{"role": "user", "content": "old chat"}])
        call = fake_sdk.chat.completions.calls[0]
        self.assertEqual(call["model"], DEFAULT_CHAT_MODEL)
        self.assertEqual(call["messages"][0]["role"], "system")
        self.assertIn("Preserve all numbers", call["messages"][0]["content"])
        payload = json.loads(call["messages"][1]["content"])
        self.assertEqual(payload["user_question"], "明天天气怎么样")
        self.assertEqual(payload["route"]["category"], "weather")
        self.assertEqual(payload["summary"], "Open-Meteo forecast for 2026-07-07")
        self.assertEqual(payload["data"]["source"], "Open-Meteo")
        self.assertEqual(payload["data"]["temperature_min_c"], 24.0)
        self.assertNotIn("finnhub_api_key", payload["data"])
        self.assertNotIn("token", payload["data"])
        self.assertNotIn("fh-secret", call["messages"][1]["content"])

    def test_naturalize_tool_answer_rejects_empty_output(self):
        fake_sdk = FakeSDKClient(chat_response=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="  "))]))

        with self.assertRaises(OpenAIClientError) as caught:
            OpenAIClient(make_settings(), sdk_client=fake_sdk).naturalize_tool_answer(
                question="AAPL stock price",
                route={"category": "stock", "tool_name": "stock_provider"},
                raw_answer="AAPL last traded at 193.12 USD. This is not trading advice.",
                summary="Finnhub quote for AAPL",
                data={"source": "Finnhub", "current_price": 193.12},
            )

        self.assertIn("naturalization returned empty text", str(caught.exception))

    def test_text_to_speech_streams_to_output_file(self):
        speech_response = FakeSpeechResponse(data=b"fake-mp3")
        fake_sdk = FakeSDKClient(speech_response=speech_response)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "nested" / "output.mp3"

            OpenAIClient(make_settings(), sdk_client=fake_sdk).text_to_speech("answer", str(output_path))

            self.assertEqual(output_path.read_bytes(), b"fake-mp3")

        call = fake_sdk.audio.speech.with_streaming_response.calls[0]
        self.assertEqual(call["model"], DEFAULT_TTS_MODEL)
        self.assertEqual(call["voice"], DEFAULT_TTS_VOICE)
        self.assertEqual(call["input"], "answer")
        self.assertEqual(call["speed"], DEFAULT_TTS_SPEED)
        self.assertNotIn("instructions", call)
        self.assertEqual(speech_response.streamed_to.name, "output.mp3")

    def test_text_to_speech_sends_configured_instructions_and_speed(self):
        speech_response = FakeSpeechResponse(data=b"styled-mp3")
        fake_sdk = FakeSDKClient(speech_response=speech_response)
        settings = make_settings()
        settings = Settings(
            **{
                **settings.__dict__,
                "tts_instructions": "Sound relaxed, confident, and lightly amused.",
                "tts_speed": 1.25,
            }
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.mp3"

            OpenAIClient(settings, sdk_client=fake_sdk).text_to_speech("answer", str(output_path))

            self.assertEqual(output_path.read_bytes(), b"styled-mp3")

        call = fake_sdk.audio.speech.with_streaming_response.calls[0]
        self.assertEqual(call["instructions"], "Sound relaxed, confident, and lightly amused.")
        self.assertEqual(call["speed"], 1.25)

    def test_missing_openai_api_key_has_actionable_error_without_sdk_import(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "input.wav"
            audio_path.write_bytes(b"wav-data")

            with self.assertRaises(OpenAIClientError) as caught:
                OpenAIClient(make_settings(openai_api_key=None)).transcribe_audio(str(audio_path))

        self.assertIn("OPENAI_API_KEY is required", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

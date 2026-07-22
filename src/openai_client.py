"""OpenAI speech and chat boundary for Hey Jarvis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableSequence

from .config import Settings, load_settings


DEFAULT_HISTORY_LIMIT = 8
CHAT_SYSTEM_PROMPT = (
    "You are Hey Jarvis, a concise macOS voice assistant. "
    "Answer spoken questions in one or two short sentences, in the user's language when it is clear. "
    "For stable, non-high-stakes knowledge questions, give the most useful best-effort answer from "
    "your available knowledge. Comparison, ambiguity, scholarly disagreement, or the fact that "
    "verification could be useful are not by themselves reasons to say that internet access is "
    "required. If a premise is broad, such as an unspecified historical period or region, briefly "
    "state the missing qualifier and then give a defensible comparison or known context. Calibrate "
    "genuine uncertainty instead of guessing or giving a bare refusal. Do not claim that you browsed, "
    "searched, checked sources, or verified current facts when you did not. For current, live, latest, "
    "or other freshness-dependent facts, do not rely on memory or speculate; use only provided tool "
    "results, or clearly say that current data cannot be verified. Treat high-stakes medical, legal, "
    "and financial guidance cautiously and do not present uncertain knowledge as professional advice."
)
TOOL_NATURALIZATION_SYSTEM_PROMPT = (
    "You are Hey Jarvis naturalizing an already-verified structured tool answer for speech. "
    "The structured data and raw answer are authoritative. Preserve all numbers, units, currencies, "
    "dates, timestamps, locations, provider or source names, caveats, and advice disclaimers. "
    "Do not add facts, recommendations, forecasts, prices, sources, or speculation. "
    "Answer in the user's language when it is clear, in one or two concise sentences."
)
_CJK_RANGE_START = "\u3400"
_CJK_RANGE_END = "\u9fff"
_EXPLICIT_ENGLISH_PATTERNS = (
    re.compile(r"(?:英文|英语|英語)(?:怎么|怎麼)?(?:说|說|读|讀|写|寫|拼|表达|表達)"),
    re.compile(r"用(?:英文|英语|英語)(?:怎么|怎麼)?(?:说|說|表达|表達|写|寫)"),
    re.compile(r"(?:怎么|怎麼)用(?:英文|英语|英語)(?:说|說|表达|表達|写|寫)"),
    re.compile(r"(?:翻译|翻譯)(?:成|为|為|到)?(?:英文|英语|英語)"),
    re.compile(r"(?:英文|英语|英語)(?:翻译|翻譯|术语|術語|名称|名稱|拼写|拼寫|发音|發音)"),
    re.compile(r"\b(?:in english|translate\b.*\bto english|english (?:term|translation|spelling|pronunciation))\b", re.IGNORECASE),
)
OPENAI_RECOVERY_GUIDANCE = (
    "Set OPENAI_API_KEY in .env or the environment and install requirements.txt "
    "before running the real assistant."
)


class OpenAIClientError(RuntimeError):
    """Raised when OpenAI configuration or requests fail."""


@dataclass
class OpenAIClient:
    """Small testable wrapper around OpenAI speech-to-text, chat, and TTS."""

    settings: Settings
    sdk_client: Any | None = None
    history_limit: int = DEFAULT_HISTORY_LIMIT

    def transcribe_audio(self, path: str) -> str:
        """Transcribe an audio file and return non-empty text."""

        audio_path = Path(path)
        if not audio_path.is_file():
            raise OpenAIClientError(f"Audio file not found for transcription: {audio_path}")

        try:
            with audio_path.open("rb") as audio_file:
                response = self._client().audio.transcriptions.create(
                    model=self.settings.transcribe_model,
                    file=audio_file,
                )
        except OpenAIClientError:
            raise
        except Exception as exc:
            raise OpenAIClientError(f"OpenAI transcription request failed: {exc}") from exc

        text = _extract_text(response, context="transcription").strip()
        if not text:
            raise OpenAIClientError("OpenAI transcription returned empty text")
        return text

    def ask_chatgpt(self, text: str, history: MutableSequence[dict[str, str]]) -> str:
        """Ask the configured chat model and update bounded in-memory history."""

        user_text = _require_text(text, "Chat input")
        history_messages = _validated_history(history)
        messages = (
            [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
            + [{"role": "system", "content": _language_policy(user_text)}]
            + history_messages[-self.history_limit :]
            + [{"role": "user", "content": user_text}]
        )

        try:
            response = self._client().chat.completions.create(
                model=self.settings.chat_model,
                messages=messages,
            )
        except OpenAIClientError:
            raise
        except Exception as exc:
            raise OpenAIClientError(f"OpenAI chat request failed: {exc}") from exc

        reply = _extract_chat_text(response).strip()
        if not reply:
            raise OpenAIClientError("OpenAI chat response returned empty text")

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        del history[:-self.history_limit]
        return reply

    def naturalize_tool_answer(
        self,
        *,
        question: str,
        route: Mapping[str, object],
        raw_answer: str,
        summary: str,
        data: Mapping[str, object],
    ) -> str:
        """Rewrite a successful structured tool answer without using chat history."""

        user_question = _require_text(question, "Tool naturalization question")
        raw_tool_answer = _require_text(raw_answer, "Tool raw answer")
        payload = {
            "user_question": user_question,
            "route": dict(route),
            "raw_answer": raw_tool_answer,
            "summary": summary,
            "data": _sanitized_tool_data(data),
        }
        messages = [
            {"role": "system", "content": TOOL_NATURALIZATION_SYSTEM_PROMPT},
            {"role": "system", "content": _language_policy(user_question)},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        ]

        try:
            response = self._client().chat.completions.create(
                model=self.settings.chat_model,
                messages=messages,
            )
        except OpenAIClientError:
            raise
        except Exception as exc:
            raise OpenAIClientError(f"OpenAI tool answer naturalization request failed: {exc}") from exc

        answer = _extract_chat_text(response).strip()
        if not answer:
            raise OpenAIClientError("OpenAI tool answer naturalization returned empty text")
        return answer

    def text_to_speech(self, text: str, output_path: str) -> None:
        """Synthesize speech to an MP3 file."""

        speech_text = _require_text(text, "TTS input")
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        speech_request = {
            "model": self.settings.tts_model,
            "voice": self.settings.tts_voice,
            "input": speech_text,
            "speed": self.settings.tts_speed,
        }
        if self.settings.tts_instructions is not None:
            speech_request["instructions"] = self.settings.tts_instructions

        try:
            response_context = self._client().audio.speech.with_streaming_response.create(**speech_request)
            with response_context as response:
                response.stream_to_file(destination)
        except OpenAIClientError:
            raise
        except Exception as exc:
            raise OpenAIClientError(f"OpenAI text-to-speech request failed: {exc}") from exc

        if not destination.is_file():
            raise OpenAIClientError(f"OpenAI text-to-speech did not write output file: {destination}")

    def _client(self) -> Any:
        if self.sdk_client is not None:
            return self.sdk_client

        if self.settings.openai_api_key is None:
            raise OpenAIClientError(f"OPENAI_API_KEY is required. {OPENAI_RECOVERY_GUIDANCE}")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIClientError(f"The openai package is not importable. {OPENAI_RECOVERY_GUIDANCE}") from exc

        self.sdk_client = OpenAI(api_key=self.settings.openai_api_key)
        return self.sdk_client


def build_openai_client(
    *,
    settings: Settings | None = None,
    sdk_client: Any | None = None,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> OpenAIClient:
    """Build the default OpenAI client wrapper from project settings."""

    return OpenAIClient(
        settings=settings or load_settings(require_openai_api_key=True),
        sdk_client=sdk_client,
        history_limit=history_limit,
    )


def transcribe_audio(path: str) -> str:
    """Transcribe an audio file with the configured OpenAI model."""

    return build_openai_client().transcribe_audio(path)


def ask_chatgpt(text: str, history: list[dict[str, str]]) -> str:
    """Ask the chat model using and updating the supplied short history."""

    return build_openai_client().ask_chatgpt(text, history)


def text_to_speech(text: str, output_path: str) -> None:
    """Write synthesized speech to an MP3 file with the configured OpenAI model."""

    build_openai_client().text_to_speech(text, output_path)


def _extract_text(response: Any, *, context: str) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, Mapping):
        value = response.get("text")
        if isinstance(value, str):
            return value
    value = getattr(response, "text", None)
    if isinstance(value, str):
        return value
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            value = dumped.get("text")
            if isinstance(value, str):
                return value
    raise OpenAIClientError(f"OpenAI {context} response did not include text")


def _extract_chat_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text

    choices = _read_value(response, "choices")
    if not choices:
        raise OpenAIClientError("OpenAI chat response did not include choices")

    message = _read_value(choices[0], "message")
    content = _read_value(message, "content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _read_value(item, "text")
            if isinstance(text, str):
                parts.append(text)
        if parts:
            return "".join(parts)

    raise OpenAIClientError("OpenAI chat response did not include message content")


def _read_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _require_text(value: str, name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise OpenAIClientError(f"{name} must not be empty")
    return stripped


def _language_policy(user_text: str) -> str:
    """Return a current-turn language instruction that outranks chat history."""

    has_cjk = any(_CJK_RANGE_START <= character <= _CJK_RANGE_END for character in user_text)
    if not has_cjk:
        return (
            "Language policy for the current request: match the current user's language; "
            "for English input, answer in English. Do not copy a different language from prior history."
        )
    if any(pattern.search(user_text) for pattern in _EXPLICIT_ENGLISH_PATTERNS):
        return (
            "Language policy for the current request: the user is asking in Chinese for English wording, "
            "translation, spelling, or pronunciation. Include the requested English content, but keep any "
            "surrounding explanation in concise Simplified Chinese. Prior chat-history language must not override this."
        )
    return (
        "Language policy for the current request: answer entirely in concise Simplified Chinese because the "
        "current request contains Chinese. Prior chat-history language must not override this instruction."
    )


def _validated_history(history: MutableSequence[dict[str, str]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            raise OpenAIClientError("Chat history entries must be dictionaries")
        role = item.get("role")
        content = item.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            raise OpenAIClientError("Chat history entries must include string role and content")
        if not role.strip() or not content.strip():
            raise OpenAIClientError("Chat history role and content must not be empty")
        messages.append({"role": role, "content": content})
    return messages


def _sanitized_tool_data(data: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in data.items():
        normalized_key = key.casefold()
        if any(marker in normalized_key for marker in ("key", "token", "secret", "credential")):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value
    return sanitized

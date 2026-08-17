"""Generate, synthesize, and promote configurable-session notification cues."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Callable

from src.config import load_settings
from src.evals.realtime_common import PROJECT_ROOT
from src.realtime_farewell_asset import finalize_streaming_wav
from src.session_expiry_cues import (
    LABELS,
    MODEL,
    VOICE,
    WARNING_PHRASES,
    SessionExpiryCueError,
    promote_selection,
    store_warning_candidate,
    synthesize_ready_tones,
)


DEFAULT_ROOT = PROJECT_ROOT / "artifacts" / "audio" / "candidates" / "session-expiry"
STYLE_VERSIONS = {
    "en": (
        "session-expiry-en-warm-v1",
        "session-expiry-en-calm-v1",
        "session-expiry-en-crisp-v1",
    ),
    "zh-CN": (
        "session-expiry-zh-warm-v1",
        "session-expiry-zh-calm-v1",
        "session-expiry-zh-crisp-v1",
    ),
}
STYLE_WORDS = {
    "warm": "warm, reassuring, friendly, and concise",
    "calm": "calm, clear, unhurried, and concise",
    "crisp": "clear, light, responsive, and concise",
}


def _instruction(locale: str, phrase: str, prompt_version: str) -> str:
    style = prompt_version.rsplit("-", 2)[1]
    language = "natural Simplified Chinese" if locale == "zh-CN" else "natural English"
    return f"Say exactly: {phrase} Speak in {language}, {STYLE_WORDS[style]}. Add no words."


def _openai_synthesizer() -> Callable[[str, str], bytes]:
    settings = load_settings(env_file=PROJECT_ROOT / ".env", require_openai_api_key=True)
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SessionExpiryCueError("The OpenAI SDK is unavailable") from exc
    client = OpenAI(api_key=settings.openai_api_key, max_retries=0)

    def synthesize(phrase: str, instructions: str) -> bytes:
        with tempfile.TemporaryDirectory(prefix="hey-jarvis-session-cue-") as temporary:
            raw_path = Path(temporary) / "candidate.wav"
            context = client.audio.speech.with_streaming_response.create(
                model=MODEL,
                voice=VOICE,
                input=phrase,
                instructions=instructions,
                response_format="wav",
            )
            with context as response:
                response.stream_to_file(raw_path)
            return finalize_streaming_wav(raw_path.read_bytes())

    return synthesize


def generate_all_warnings(
    *,
    root: Path = DEFAULT_ROOT,
    owner_authorized: bool,
    synthesizer: Callable[[str, str], bytes] | None = None,
) -> list[dict[str, object]]:
    if not owner_authorized:
        raise SessionExpiryCueError("Explicit owner authorization is required for paid generation")
    synthesize = synthesizer or _openai_synthesizer()
    results = []
    for locale in ("en", "zh-CN"):
        phrase = WARNING_PHRASES[locale]
        for label, prompt_version in zip(LABELS, STYLE_VERSIONS[locale], strict=True):
            # Deliberately one call per candidate with no automatic retry.
            wav_data = synthesize(phrase, _instruction(locale, phrase, prompt_version))
            results.append(
                store_warning_candidate(
                    root,
                    locale=locale,
                    label=label,
                    wav_data=wav_data,
                    transcript=phrase,
                    prompt_version=prompt_version,
                )
            )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.session_expiry_cues")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate-warnings")
    generate.add_argument("--owner-authorized", action="store_true")
    commands.add_parser("synthesize-tones")
    promote = commands.add_parser("promote")
    promote.add_argument("--english", required=True, type=Path)
    promote.add_argument("--chinese", required=True, type=Path)
    promote.add_argument("--ready", required=True, type=Path)
    promote.add_argument("--owner-confirmed", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate-warnings":
            result = generate_all_warnings(owner_authorized=args.owner_authorized)
        elif args.command == "synthesize-tones":
            result = synthesize_ready_tones(DEFAULT_ROOT)
        else:
            result = promote_selection(
                project_root=PROJECT_ROOT,
                english=args.english,
                chinese=args.chinese,
                ready=args.ready,
                confirmed_by_owner=args.owner_confirmed,
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, SessionExpiryCueError) as exc:
        print(f"Session expiry cue failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate, validate, audition, and promote the cached Mandarin farewell."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from src.config import load_settings
from src.evals.realtime_common import PROJECT_ROOT
from src.realtime_farewell_asset import (
    CANDIDATE_LABEL,
    FAREWELL_GENERATION_MODEL,
    FAREWELL_PHRASE,
    RealtimeFarewellAssetError,
    finalize_streaming_wav,
    promote_candidate,
    store_candidate,
)


DEFAULT_CANDIDATE_ROOT = PROJECT_ROOT / "artifacts" / "audio" / "candidates" / "mandarin-farewell"
DELIVERY_STYLES = {
    "warm": (
        "mandarin-farewell-v1",
        "Speak exactly 再见 in warm, natural Mandarin Chinese. Do not add any other words.",
    ),
    "soft": (
        "mandarin-farewell-soft-v1",
        "Speak exactly 再见 in soft, relaxed, gentle Mandarin Chinese. Keep the voice light, friendly, and unforced, with a subtle smile. Do not sound stern, intense, clenched, or dramatic. Do not add any other words.",
    ),
    "light": (
        "mandarin-farewell-light-v1",
        "Speak exactly 再见 in light, casual, friendly Mandarin Chinese, like an easy everyday goodbye to a friend. Use a small natural lift and relaxed articulation. Do not sound heavy, forceful, formal, or dramatic. Do not add any other words.",
    ),
}


def generate_candidate(label: str, *, owner_authorized: bool, style: str = "warm") -> dict[str, object]:
    if not owner_authorized:
        raise RealtimeFarewellAssetError("Explicit owner authorization is required for paid generation")
    if not CANDIDATE_LABEL.fullmatch(label):
        raise RealtimeFarewellAssetError("Farewell candidate label must look like candidate-01")
    if style not in DELIVERY_STYLES:
        raise RealtimeFarewellAssetError("Farewell style was invalid")
    prompt_version, instructions = DELIVERY_STYLES[style]
    settings = load_settings(env_file=PROJECT_ROOT / ".env", require_openai_api_key=True)
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RealtimeFarewellAssetError("The OpenAI SDK is unavailable") from exc
    client = OpenAI(api_key=settings.openai_api_key)
    with tempfile.TemporaryDirectory(prefix="hey-jarvis-farewell-") as temporary:
        raw_path = Path(temporary) / "farewell.wav"
        try:
            context = client.audio.speech.with_streaming_response.create(
                model=FAREWELL_GENERATION_MODEL,
                voice="alloy",
                input=FAREWELL_PHRASE,
                instructions=instructions,
                response_format="wav",
            )
            with context as response:
                response.stream_to_file(raw_path)
        except Exception as exc:
            raise RealtimeFarewellAssetError(f"OpenAI farewell generation failed: {exc}") from exc
        return store_candidate(
            DEFAULT_CANDIDATE_ROOT,
            label=label,
            wav_data=finalize_streaming_wav(raw_path.read_bytes()),
            transcript=FAREWELL_PHRASE,
            model=FAREWELL_GENERATION_MODEL,
            voice="alloy",
            output_gain=settings.realtime_output_volume,
            prompt_version=prompt_version,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.realtime_farewell_asset")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="make one paid Mandarin farewell candidate")
    generate.add_argument("label")
    generate.add_argument("--owner-authorized", action="store_true")
    generate.add_argument("--style", choices=tuple(DELIVERY_STYLES), default="warm")
    promote = commands.add_parser("promote", help="promote an auditioned farewell candidate")
    promote.add_argument("candidate", type=Path)
    promote.add_argument("--owner-confirmed", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            result = generate_candidate(
                args.label,
                owner_authorized=args.owner_authorized,
                style=args.style,
            )
        else:
            result = promote_candidate(
                args.candidate,
                project_root=PROJECT_ROOT,
                confirmed_by_owner=args.owner_confirmed,
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, RealtimeFarewellAssetError) as exc:
        print(f"Realtime farewell asset failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

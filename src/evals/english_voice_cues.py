"""Generate and promote owner-selected English cached voice cues."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from src.config import load_settings
from src.english_voice_cues import (
    CANDIDATE_LABEL,
    MODEL,
    PLAYBACK_GAIN,
    VOICE,
    EnglishVoiceCueError,
    cue_spec,
    prepare_selected_assets,
    promote_candidate,
    store_candidate,
)
from src.evals.realtime_common import PROJECT_ROOT
from src.realtime_farewell_asset import finalize_streaming_wav


DEFAULT_CANDIDATE_ROOT = PROJECT_ROOT / "tmp" / "realtime-english-cue-candidates"
STYLES = {
    "ack": {
        "light": "english-ack-light-v1",
        "warm": "english-ack-warm-v1",
        "crisp": "english-ack-crisp-v1",
    },
    "farewell": {
        "light": "english-farewell-light-v1",
        "warm": "english-farewell-warm-v1",
        "casual": "english-farewell-casual-v1",
    },
}
INSTRUCTIONS = {
    "english-ack-light-v1": "Say exactly: I'm here. Yes? Use a light, friendly, natural tone. Keep both sentences clear and brief. Add no words.",
    "english-ack-warm-v1": "Say exactly: I'm here. Yes? Sound warm, attentive, relaxed, and concise. Add no words.",
    "english-ack-crisp-v1": "Say exactly: I'm here. Yes? Sound clear, responsive, easygoing, and not heavy or formal. Add no words.",
    "english-farewell-light-v1": "Say exactly: See you. Use a light, friendly, natural goodbye. Add no words.",
    "english-farewell-warm-v1": "Say exactly: See you. Sound warm, relaxed, and brief, with a subtle smile. Add no words.",
    "english-farewell-casual-v1": "Say exactly: See you. Sound casual, easygoing, and unforced, like saying goodbye to a friend. Add no words.",
}


def generate_candidate(cue: str, label: str, *, style: str, owner_authorized: bool) -> dict[str, object]:
    if not owner_authorized:
        raise EnglishVoiceCueError("Explicit owner authorization is required for paid generation")
    if not CANDIDATE_LABEL.fullmatch(label) or label not in {"candidate-01", "candidate-02", "candidate-03"}:
        raise EnglishVoiceCueError("Paid generation is bounded to candidate-01 through candidate-03")
    try:
        prompt_version = STYLES[cue][style]
    except KeyError as exc:
        raise EnglishVoiceCueError("English cue style was invalid") from exc
    spec = cue_spec(cue)
    settings = load_settings(env_file=PROJECT_ROOT / ".env", require_openai_api_key=True)
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise EnglishVoiceCueError("The OpenAI SDK is unavailable") from exc
    client = OpenAI(api_key=settings.openai_api_key)
    with tempfile.TemporaryDirectory(prefix=f"hey-jarvis-en-{cue}-") as temporary:
        raw_path = Path(temporary) / f"{cue}.wav"
        try:
            context = client.audio.speech.with_streaming_response.create(
                model=MODEL,
                voice=VOICE,
                input=spec.phrase,
                instructions=INSTRUCTIONS[prompt_version],
                response_format="wav",
            )
            with context as response:
                response.stream_to_file(raw_path)
        except Exception as exc:
            raise EnglishVoiceCueError(f"OpenAI English {cue} generation failed: {exc}") from exc
        return store_candidate(
            DEFAULT_CANDIDATE_ROOT,
            cue=cue,
            label=label,
            wav_data=finalize_streaming_wav(raw_path.read_bytes()),
            transcript=spec.phrase,
            prompt_version=prompt_version,
            output_gain=PLAYBACK_GAIN,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.evals.english_voice_cues")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("cue", choices=tuple(STYLES))
    generate.add_argument("label")
    generate.add_argument("--style", required=True)
    generate.add_argument("--owner-authorized", action="store_true")
    promote = commands.add_parser("promote")
    promote.add_argument("candidate", type=Path)
    promote.add_argument("--owner-confirmed", action="store_true")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--destination", type=Path, default=PROJECT_ROOT / "var")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            result = generate_candidate(args.cue, args.label, style=args.style, owner_authorized=args.owner_authorized)
        elif args.command == "promote":
            result = promote_candidate(args.candidate, project_root=PROJECT_ROOT, confirmed_by_owner=args.owner_confirmed)
        else:
            result = prepare_selected_assets(project_root=PROJECT_ROOT, destination=args.destination)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, EnglishVoiceCueError) as exc:
        print(f"English voice cue failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

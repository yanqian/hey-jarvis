# Hey Jarvis

Hey Jarvis is a simple macOS voice assistant MVP.

The accepted first demo flow is:

```text
User: "Hey Jarvis, what is two plus two?"
Assistant: "Two plus two is four."
```

## Status

This project is currently at the runnable skeleton stage. The checked-in code proves the Python package, tests, and recovery entrypoint work without requiring a microphone, speakers, or OpenAI credentials. Audio capture, wake-word detection, and OpenAI client boundaries are implemented behind testable modules; the full assistant state machine and playback wiring are planned in the harness feature list.

## Runtime

Use Python 3.11 or Python 3.12 for the MVP. Some audio and ML dependencies may not yet support newer Python releases.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.main --dry-run
```

To inspect local runtime readiness without starting the assistant:

```bash
python -m src.main --diagnose
```

When the full MVP is implemented, run:

```bash
python -m src.main
```

## OpenAI Configuration

Set `OPENAI_API_KEY` in `.env` before running any real transcription, chat, or speech synthesis path. The MVP defaults are:

```text
TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
CHAT_MODEL=gpt-4o-mini
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=alloy
```

The automated recovery check uses fakes and dry-run paths, so it does not make live OpenAI API calls.

## Recovery Check

From the repository root:

```bash
./init.sh
```

The recovery check runs the AI Agent Harness verification, compiles project Python files, runs tests, and executes the dry-run smoke path.

## Notes

- The first MVP wake phrase is `Hey Jarvis`.
- Custom wake words are deferred to a later iteration; the MVP uses the built-in openWakeWord Hey Jarvis model.
- macOS microphone permission must be granted to the terminal or agent surface that launches the assistant before the real demo can run.
- Playback will use macOS `afplay` in the MVP.

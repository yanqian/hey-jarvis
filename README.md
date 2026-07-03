# Hey Jarvis

Hey Jarvis is a simple macOS voice assistant MVP.

The accepted first demo flow is:

```text
User: "Hey Jarvis, what is two plus two?"
Assistant: "Two plus two is four."
```

## Status

This project now includes the MVP voice-assistant loop behind testable boundaries. The recovery entrypoint proves the Python package, tests, and a fake-backend state-machine path work without requiring a microphone, speakers, or OpenAI credentials. Real audio capture, wake-word detection, OpenAI transcription/chat/TTS, and macOS playback are wired through `python -m src.main`.

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

For the dependency-free full-flow smoke path:

```bash
python -m src.main --fake-backend
```

## Real Demo

Before the real demo, run `python -m src.main --diagnose` and fix any reported errors. Grant macOS microphone permission to the terminal or agent surface that launches the assistant, and make sure `.env` contains a real `OPENAI_API_KEY`.

Start the assistant:

```bash
python -m src.main
```

Say `Hey Jarvis`, then ask `what is two plus two?`. The app records the question, transcribes it, asks the configured chat model, writes `tmp/output.mp3`, plays it through `afplay`, and returns to `WAIT_WAKE` for the next wake phrase.

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

The recovery check runs the AI Agent Harness verification, compiles project Python files, runs tests, and executes dry-run plus fake-backend smoke paths.

## Notes

- The first MVP wake phrase is `Hey Jarvis`.
- Custom wake words are deferred to a later iteration; the MVP uses the built-in openWakeWord Hey Jarvis model.
- macOS microphone permission must be granted to the terminal or agent surface that launches the assistant before the real demo can run.
- Playback will use macOS `afplay` in the MVP.

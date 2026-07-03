# Hey Jarvis

Hey Jarvis is a simple macOS voice assistant MVP.

The accepted first demo flow is:

```text
User: "Hey Jarvis, what is two plus two?"
Assistant: "Two plus two is four."
```

## Status

This project is currently at the runnable skeleton stage. The checked-in code proves the Python package, tests, and recovery entrypoint work without requiring a microphone, speakers, or OpenAI credentials. Real audio capture, wake-word detection, OpenAI calls, and playback are planned in the harness feature list.

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

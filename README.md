# Hey Jarvis

Hey Jarvis is a simple macOS voice assistant MVP.

The accepted first demo flow is:

```text
User: "Alexa, what is two plus two?"
Assistant: "Two plus two is four."
```

## Status

This project now includes the MVP voice-assistant loop behind testable boundaries. The recovery entrypoint proves the Python package, tests, and a fake-backend state-machine path work without requiring a microphone, speakers, or OpenAI credentials. Real audio capture, wake-word detection, OpenAI transcription/chat/TTS, and macOS playback are wired through `python -m src.main`.

## Runtime

Use Python 3.11 or Python 3.12 for the MVP. Some audio and ML dependencies may not yet support newer Python releases.

## Setup

Create an isolated Python environment, install the runtime dependencies, create
local configuration, and run the dependency-free smoke path:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.main --prepare-wake-word
python -m src.main --dry-run
```

Edit `.env` and replace the placeholder OpenAI key:

```text
OPENAI_API_KEY=sk-...
```

The real assistant requires the packages in `requirements.txt`, an
`OPENAI_API_KEY`, macOS microphone permission, and macOS `afplay` playback.
The runtime dependency set is `sounddevice`, `numpy`, `scipy`, `openai`,
`openwakeword`, `onnxruntime`, and `python-dotenv`.

Wake-word detection uses the openWakeWord Alexa ONNX model through
`onnxruntime`. The model files are prepared explicitly so setup failures are
visible before microphone capture starts:

```bash
python -m src.main --prepare-wake-word
```

To inspect local runtime readiness without starting the assistant, run:

```bash
python -m src.main --diagnose
```

For the dependency-free full-loop smoke path, run:

```bash
python -m src.main --fake-backend
```

To inspect wake-word behavior without OpenAI or playback, run a wake debug
probe:

```bash
python -m src.main --wake-debug
```

To save the exact live microphone audio that was scored, pass an explicit debug
output path:

```bash
python -m src.main --wake-debug --wake-debug-output tmp/wake-debug.wav
```

To score an existing 16-bit mono WAV file without microphone access, run:

```bash
python -m src.main --wake-file tmp/wake-debug.wav
```

To start the real assistant, run:

```bash
python -m src.main
```

## Real Demo

Before the real demo, run `python -m src.main --prepare-wake-word`, then
`python -m src.main --diagnose`, and fix any reported errors. Grant macOS
microphone permission to the terminal or agent surface that launches the
assistant, and make sure `.env` contains a real `OPENAI_API_KEY`.

Start the assistant:

```bash
python -m src.main
```

Say `Alexa`, then ask `what is two plus two?`. The app records the question, transcribes it, asks the configured chat model, writes `tmp/output.mp3`, plays it through `afplay`, and returns to `WAIT_WAKE` for the next wake phrase.

The accepted first MVP wake phrase is `Alexa`; custom wake-word model
loading is deferred to a later iteration.

## macOS Permissions And Playback

Hey Jarvis uses the microphone continuously while waiting for the wake phrase.
Grant microphone access to the launching app in System Settings:

```text
System Settings -> Privacy & Security -> Microphone
```

Enable the terminal or agent surface that runs `python -m src.main`, then restart
that app before trying the real demo again.

Playback uses the macOS `afplay` command. `python -m src.main --diagnose`
reports whether `afplay` is available on `PATH`. The automated recovery checks
do not require speakers because `--dry-run` and `--fake-backend` avoid real
playback.

## OpenAI Configuration

Set `OPENAI_API_KEY` in `.env` before running any real transcription, chat, or speech synthesis path. The MVP defaults are:

```text
WAKE_PHRASE=alexa
WAKE_THRESHOLD=0.5
SILENCE_SECONDS=1.5
MAX_RECORD_SECONDS=20
SAMPLE_RATE=16000
TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
CHAT_MODEL=gpt-4o-mini
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=alloy
WAKE_DEBUG=0
```

The automated recovery check uses fakes and dry-run paths, so it does not make live OpenAI API calls.

## Wake-Word Debugging

Use `python -m src.main --wake-debug` when the assistant remains in `WAIT_WAKE`
and you need to see live microphone levels and wake-word scores without making
OpenAI requests or playing audio. Each line includes `rms`, `peak`, `overflow`,
`score`, `threshold`, and `detected`. Scores are printed with enough precision
to tell true zeros from tiny non-zero model outputs, followed by a summary with
the frame count, maximum observed score, threshold, and detected frame count.

Use an explicit output file when you need a reproducible record-and-replay
workflow:

```bash
python -m src.main --wake-debug --wake-debug-output tmp/wake-debug.wav
python -m src.main --wake-file tmp/wake-debug.wav
```

Wake debug does not create or overwrite `tmp/input.wav` unless you explicitly
choose that path with `--wake-debug-output`; normal question recording still owns
`tmp/input.wav`.

Use `python -m src.main --wake-file tmp/wake-debug.wav` to score a saved WAV
clip without microphone access. The file must be mono 16-bit PCM. Short final
chunks are scored and included in the summary instead of being silently ignored.
This is useful when you want to compare a recorded phrase against the configured
`WAKE_THRESHOLD`.

Set `WAKE_DEBUG=1` in `.env` to log the same wake-word score fields during
normal `WAIT_WAKE` listening.

Common outcomes:

- `rms` and `peak` stay near `0`: the app is receiving silence; check macOS
  microphone permission, input device selection, and physical input level.
- `overflow=true`: microphone capture or wake-word processing fell behind; close
  CPU-heavy processes and confirm the wake-word model is prepared before
  listening.
- `score` rises but stays below `threshold`: lower `WAKE_THRESHOLD` cautiously or
  speak the accepted `Alexa` phrase more clearly.
- `score` stays low while `rms` and `peak` move: the microphone is working, but
  openWakeWord is not matching the phrase; check pronunciation, distance, and
  background noise.

## Troubleshooting

- `OPENAI_API_KEY is required`: copy `.env.example` to `.env` and replace the
  placeholder value.
- `sounddevice is not importable`, `openai is not importable`, or another
  dependency is missing: activate `.venv` and run `pip install -r
  requirements.txt`.
- `wake_word_models` reports missing files: activate `.venv` and run `python -m
  src.main --prepare-wake-word`, then run `python -m src.main --diagnose` again.
- `onnxruntime is not importable`: activate `.venv` and run `pip install -r
  requirements.txt`; the MVP wake-word path uses ONNX models.
- Microphone capture fails or records silence: confirm the launching terminal has
  macOS microphone permission, then restart that terminal.
- Microphone input overflows while the app is in `WAIT_WAKE`: the wake-word
  model may still be starting up or audio processing may have fallen behind.
  Run `python -m src.main --prepare-wake-word`, restart the app, and close other
  CPU-heavy audio or ML processes before trying the wake phrase again.
- Playback fails: run `python -m src.main --diagnose` and confirm `afplay` is
  available. The MVP is macOS-only for playback.
- Wake-word detection does not trigger: use the accepted phrase `Alexa`,
  speak clearly near the microphone, confirm the app is still in `WAIT_WAKE`,
  then run `python -m src.main --wake-debug` or set `WAKE_DEBUG=1` to inspect
  microphone levels and wake scores.

## Recovery Check

From the repository root:

```bash
./init.sh
```

The recovery check runs the AI Agent Harness verification, compiles project Python files, runs tests, and executes dry-run plus fake-backend smoke paths.

## Post-MVP TODOs

- Interrupt playback when the user says `Alexa` while audio is still
  playing.
- Keep listening for a six-second follow-up question after each answer before
  returning to wake-word-only mode.
- Add configurable custom wake-word model loading instead of only using the
  built-in openWakeWord Alexa model.

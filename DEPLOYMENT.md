# Deployment

Hey Jarvis is deployed as a local macOS Python process. It is not a server
deployment: the runtime needs the local microphone, the local speaker path
through `afplay`, OpenAI credentials, and the openWakeWord Alexa TFLite model
files on the same machine that launches the assistant.

## Supported Target

- macOS with microphone access for the launching terminal or agent surface.
- Python 3.11 or Python 3.12.
- `afplay` available on `PATH`.
- Network access during setup for Python packages and wake-word model downloads.
- A valid `OPENAI_API_KEY` for real transcription, chat, and text-to-speech.

The active wake-word path is openWakeWord's built-in Alexa model with TFLite:

```text
WAKE_BACKEND=openwakeword
WAKE_MODEL=alexa
WAKE_INFERENCE_FRAMEWORK=tflite
WAKE_PHRASE=alexa
WAKE_THRESHOLD=0.5
```

On macOS ARM64, do not deploy with `WAKE_INFERENCE_FRAMEWORK=onnx`; the project
intentionally uses TFLite there because local debugging found ONNX Alexa scores
collapsed near zero while TFLite produced usable scores.

## Install

From a fresh checkout:

```bash
cd /path/to/hey-jarvis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
test -f .env || cp .env.example .env
```

Edit `.env` and replace the placeholder key:

```text
OPENAI_API_KEY=sk-...
```

If the TFLite runtime is missing after installing requirements, run the same
install command again from the active virtual environment and confirm
`ai-edge-litert` is installed on macOS:

```bash
python -m pip show ai-edge-litert
```

## Prepare Wake-Word Models

Download the configured openWakeWord TFLite model files before starting
microphone capture:

```bash
python -m src.main --prepare-wake-word
```

This prepares the Alexa model plus the required feature models. Re-run the
command after changing `WAKE_MODEL` or `WAKE_INFERENCE_FRAMEWORK`.

## Verify

Run the project recovery check first. This does not require microphone access,
speakers, or live OpenAI calls:

```bash
./init.sh
```

For the smallest dependency-free application smoke path:

```bash
python -m src.main --dry-run
```

Then verify the local runtime configuration:

```bash
python -m src.main --diagnose
```

Fix every `[ERROR]` before starting the real assistant. Common deployment
blockers are missing `OPENAI_API_KEY`, missing `ai-edge-litert`, missing
wake-word model files, or microphone permission not yet granted to the launching
app.

For an end-to-end state-machine smoke test without hardware or OpenAI:

```bash
python -m src.main --fake-backend
```

## Microphone Permission

Grant microphone access to the exact app that launches Hey Jarvis:

```text
System Settings -> Privacy & Security -> Microphone
```

Enable Terminal, iTerm, Codex, or whichever app runs `python -m src.main`, then
restart that app before testing live audio. macOS permission changes often do
not apply to already-running terminal sessions.

## Wake-Word Acceptance Test

Before running the full assistant, test live wake-word scoring without OpenAI or
playback:

```bash
python -m src.main --wake-debug --wake-debug-output tmp/wake-debug.wav
```

Say `Alexa` clearly near the microphone. Stop the command with `Ctrl-C`, then
replay the captured file through the same scorer:

```bash
python -m src.main --wake-file tmp/wake-debug.wav
```

Healthy output should show non-zero `rms` and `peak` values, `framework=tflite`,
and wake scores that can cross `WAKE_THRESHOLD` when the phrase is spoken
clearly. If levels move but scores stay low, lower `WAKE_THRESHOLD` cautiously
or improve microphone placement before changing code.

## Run

Start the real assistant:

```bash
python -m src.main
```

For the accepted MVP demo, say:

```text
Alexa, what is two plus two?
```

The assistant should record the question to `tmp/input.wav`, transcribe it, ask
the configured chat model, write speech to `tmp/output.mp3`, play it with
`afplay`, and return to `WAIT_WAKE`.

Stop the process with `Ctrl-C`.

## Update Or Redeploy

After pulling new code:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --prepare-wake-word
./init.sh
python -m src.main --diagnose
```

Only start the real assistant after recovery and diagnostics pass.

## Runtime Files

- `.env`: local secrets and runtime settings. Do not commit it.
- `.env.example`: documented deployable defaults.
- `tmp/input.wav`: latest normal question recording.
- `tmp/output.mp3`: latest synthesized answer.
- `tmp/wake-debug.wav`: optional wake-debug capture when requested.

## Troubleshooting

- `OPENAI_API_KEY is required`: set a real key in `.env`.
- `OpenAI transcription returned empty text`: the recorded question did not
  contain usable speech. The assistant logs the recoverable error and returns to
  `WAIT_WAKE`; try again closer to the microphone or reduce background noise.
- `LiteRT/TFLite runtime is not importable`: activate `.venv`, run
  `pip install -r requirements.txt`, then confirm `python -m pip show
  ai-edge-litert`.
- `wake_word_models` reports missing files: run `python -m src.main
  --prepare-wake-word`, then run `python -m src.main --diagnose` again.
- `WAKE_INFERENCE_FRAMEWORK=onnx` fails on macOS ARM64: keep
  `WAKE_INFERENCE_FRAMEWORK=tflite`.
- `rms` and `peak` stay near zero during `--wake-debug`: grant microphone
  permission, choose the correct input device, and restart the launching app.
- `overflow=true`: close CPU-heavy processes and make sure wake-word models were
  prepared before listening.
- Playback fails: run `python -m src.main --diagnose` and confirm `afplay` is
  available.

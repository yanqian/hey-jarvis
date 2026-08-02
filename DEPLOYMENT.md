# Deployment

Hey Jarvis remains runnable as a local macOS Python process. It also has a
product-owned Tauri application packaged as an Apple Silicon
`INTERNAL-UNSIGNED` DMG for owner-led and explicitly trusted testing. The DMG
is neither Developer ID signed nor notarized and must not be published as a
general download. It is a packaged application, but not a publicly
distributable one. See
[docs/INTERNAL_MAC_APP_TESTING.md](docs/INTERNAL_MAC_APP_TESTING.md).

## Supported target

- macOS with microphone access for the launching terminal or agent surface
- Python 3.11 or Python 3.12
- `afplay` available on `PATH`
- network access for package/model downloads and real API calls
- a valid `OPENAI_API_KEY`

Python 3.14 compatibility is not established for all audio and ML dependencies.
On Apple Silicon, use the default TFLite wake path rather than ONNX.

The required runtime packages are `sounddevice`, `numpy`, `scipy`, `openai`,
`openwakeword`, `ai-edge-litert`, and `python-dotenv`.

## Install

From a fresh checkout:

```bash
cd /path/to/hey-jarvis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
test -f .env || cp .env.example .env
```

Edit `.env`:

```text
OPENAI_API_KEY=sk-...
```

The checked-in defaults and every supported key are described in
[docs/CONFIGURATION.md](docs/CONFIGURATION.md).

Optional WebRTC VAD support is disabled by default. Install its compatible
dependency set only when you intend to enable it:

```bash
python -m pip install -r requirements-vad.txt
```

## Prepare

Download the configured openWakeWord Hey Jarvis TFLite model and feature
models:

```bash
python -m src.main --prepare-wake-word
```

Generate the local wake acknowledgement (`var/ack.mp3` by default):

```bash
python -m src.main --prepare-acknowledgement
```

Repeat these commands after changing the relevant model/framework or
acknowledgement text/path settings.

## Verify

First run the dependency-free repository recovery contract:

```bash
./init.sh
```

Then check the real machine without starting the assistant:

```bash
python -m src.main --diagnose
```

Diagnostics check dependencies, the OpenAI key without printing it, `afplay`,
wake-word model files, acknowledgement audio, configured VAD, and Realtime host
readiness.

Useful non-live checks:

```bash
python -m src.main --dry-run
python -m src.main --fake-backend
python -m src.realtime.fake_smoke
python -m src.main --text "2 + 2"
```

## Grant microphone permission

Open:

```text
System Settings → Privacy & Security → Microphone
```

Enable the terminal or agent surface that runs Hey Jarvis, then restart that
app. Realtime also needs Chrome microphone permission for its local app-mode
host.

## Run the pipeline

The pipeline remains the default:

```bash
python -m src.main
```

Say “Hey Jarvis”, wait for the local acknowledgement, then speak. The assistant
records to `tmp/input.wav`, transcribes, routes or answers, writes
`tmp/output.mp3`, plays it with `afplay`, and returns to wake listening.

For pipeline behavior and safe tool boundaries, see
[docs/PIPELINE.md](docs/PIPELINE.md).

## Run Realtime

Realtime WebRTC is opt-in:

```bash
python -m src.main --backend realtime
```

Click **Enable voice assistant** once per launched Chrome host. Python owns the
microphone before wake; after confirmed wake and acknowledgement it closes its
capture before Chrome opens WebRTC media. Follow-up turns and interruption then
stay inside the same session until an end phrase/tool, timeout, explicit stop,
transport error, or Ctrl+C.

Realtime is billable and remains a developer MVP. Read
[docs/REALTIME.md](docs/REALTIME.md) before changing volume, VAD, privacy, or
live evaluation settings.

## Wake acceptance

Inspect wake scoring without calling OpenAI or playing audio:

```bash
python -m src.main --wake-debug
python -m src.main --wake-debug --wake-debug-output tmp/wake-debug.wav
python -m src.main --wake-file tmp/wake-debug.wav
```

The output reports frame count, RMS, peak, overflow, score, threshold, maximum
observed score, and detected frames. `tmp/input.wav` remains reserved for normal
question recording unless explicitly selected as the debug output.

Lower-level model comparison is available through:

```bash
python scripts/debug_oww_file.py tmp/wake-debug.wav hey_jarvis tflite
```

Detailed real-device acceptance belongs in
[MANUAL_TESTING.md](MANUAL_TESTING.md).

## Update or redeploy

After pulling new code:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --prepare-wake-word
python -m src.main --prepare-acknowledgement
./init.sh
python -m src.main --diagnose
```

Review `.env.example` for new settings. Do not overwrite an existing `.env`
because it contains local credentials and tuning.

The internal Mac app uses manual DMG replacement and a retained prior DMG for
rollback. It does not use this source-update procedure or an automatic updater.

## Local runtime files

- `.env` — local configuration and secrets; do not commit.
- `var/ack.mp3` — generated wake acknowledgement.
- `tmp/input.wav` — most recent pipeline question recording.
- `tmp/output.mp3` — most recent pipeline synthesized answer.
- `tmp/realtime-fixtures/` — private local Realtime fixtures.
- `tmp/realtime-evals/` — local sanitized evaluation evidence.

For symptoms and recovery steps, use
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

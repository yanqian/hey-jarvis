# Troubleshooting

Start with:

```bash
source .venv/bin/activate
./init.sh
python -m src.main --diagnose
```

Fix diagnostic errors before running real audio.

## Credentials and dependencies

### `OPENAI_API_KEY is required`

Copy `.env.example` to `.env` and replace the placeholder. Diagnostics report
configured/missing without printing the value.

### A dependency is not importable

```bash
python -m pip install -r requirements.txt
```

For `dependency:webrtcvad`, install the optional compatible set only when using
`VAD_BACKEND=webrtc`:

```bash
python -m pip install -r requirements-vad.txt
```

### Wake model or TFLite is missing

```bash
python -m pip show ai-edge-litert
python -m src.main --prepare-wake-word
python -m src.main --diagnose
```

On macOS ARM64 use `WAKE_INFERENCE_FRAMEWORK=tflite`. Explicit ONNX selection
is unsupported on that target because local trials produced near-zero wake
scores.

### Acknowledgement audio is missing

Restore the checked-in accepted asset without an OpenAI key or network call:

```bash
python -m src.main --prepare-acknowledgement
```

The canonical source is `assets/wake_acknowledgement_alloy.mp3` and the default
runtime path is `var/ack.mp3`. Preparation and the
`wake_acknowledgement_audio` diagnostic validate duration plus the exact
accepted SHA-256 before atomic installation; a missing, corrupt, changed,
excessive, or near-silent replacement preserves the prior runtime asset.
`--diagnose` reports the bounded duration and integrity status.

## Microphone and wake word

Grant microphone permission to the terminal or agent surface in:

```text
System Settings → Privacy & Security → Microphone
```

Restart that app after changing permission.

If wake detection does not trigger:

```bash
python -m src.main --wake-debug
python -m src.main --wake-debug --wake-debug-output tmp/wake-debug.wav
python -m src.main --wake-file tmp/wake-debug.wav
```

Interpret the output:

- near-zero `rms` and `peak` means the app is receiving silence;
- `overflow=true` means audio processing may have fallen behind;
- a moving score below `WAKE_THRESHOLD` means the microphone works but the
  model has not accepted the phrase;
- a low score with healthy input suggests pronunciation, distance, room noise,
  model, or framework mismatch.

Prepare the model before listening and close CPU-heavy audio/ML processes if
microphone input overflows in `WAIT_WAKE`.

## Recording and acknowledgement

If acknowledgement immediately causes recording or another wake, keep the ACK
guard, post-playback cooldown, observed-quiet gate, and consecutive wake
confirmation enabled. Lower playback volume or use a shorter acknowledgement
if speaker echo clips.

`armed_summary` and `armed_trigger` show RMS, peak, overflow, noise-floor,
baseline, sustained-window, optional VAD, and pre-roll decisions. A normal
trigger should show `baseline_ready=true` and `noise_floor_has_samples=true`.

If a question waits until maximum duration, inspect `stopped_by` and room noise.
Tune `RECORDING_SILENCE_RMS` cautiously or use the optional recording VAD only
after completing the manual acceptance cases.

`OpenAI transcription returned empty text` is recoverable: the assistant skips
downstream answer stages and returns to wake listening. Speak closer to the
microphone and reduce background noise.

## Playback

Run diagnostics and confirm `afplay` is available. The recovery and fake smoke
paths do not require speakers.

Acknowledgement playback reads its duration through `afinfo` and invokes
`afplay -t` with that exact value. A duration-read, start, or runtime failure
fails closed before Realtime input is enabled. Normal answer playback does not
use this time limit. Use `--benchmark-acknowledgement` for the privacy-safe
legacy/bounded comparison; acoustic onset remains unmeasured.

If playback residue retriggers wake detection, increase
`POST_PLAYBACK_WAKE_COOLDOWN_SECONDS` or `POST_PLAYBACK_QUIET_SECONDS`
conservatively and repeat the relevant manual test.

## Provider-backed tools

Weather uses Open-Meteo, FX uses Frankfurter, and stocks use Finnhub. Network,
HTTP, timeout, missing-field, and malformed-data errors return structured tool
errors rather than speculative chat.

Set `FINNHUB_API_KEY` for stock quotes. Unknown symbols or missing/zero current
prices remain tool errors and do not fall through to general chat.

Inspect routing without OpenAI naturalization:

```bash
python -m src.main --text "明天天气怎么样"
python -m src.main --text "100 USD to SGD"
python -m src.main --text "AAPL stock price"
```

## Realtime host

Confirm the backend was started with `--backend realtime`, Chrome opened the
local app-mode host, and **Arm hands-free audio** was clicked once for this host
launch. Grant Chrome microphone permission when prompted.

Use:

```bash
python -m src.main --backend realtime --diagnose
```

The host binds to loopback by default. Do not expose it publicly. If
interruption fails, use the F060 diagnosis in [Realtime guide](REALTIME.md)
before changing volume or server VAD. If cleanup fails, stop the process with
Ctrl+C and verify Chrome released media before restarting.

## Still failing?

Find the closest real-device procedure in
[MANUAL_TESTING.md](../MANUAL_TESTING.md). Keep `tmp/debug.log`, audio fixtures,
and eval evidence local; they may contain sensitive environmental details even
when transcript-free.

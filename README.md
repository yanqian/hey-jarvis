# Hey Jarvis

Hey Jarvis is a simple macOS voice assistant MVP.

The accepted first demo flow is:

```text
User: "Hey Jarvis, what is two plus two?"
Assistant: "The answer is 4."
```

## Status

This project now includes the MVP voice-assistant loop behind testable boundaries. The recovery entrypoint proves the Python package, tests, and a fake-backend state-machine path work without requiring a microphone, speakers, or OpenAI credentials. Real audio capture, wake-word detection, OpenAI transcription/chat/TTS, and macOS playback are wired through `python -m src.main`.

For full local macOS deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).
For manual acceptance cases, see [MANUAL_TESTING.md](MANUAL_TESTING.md).

## Runtime

Use Python 3.11 or Python 3.12 for the MVP. Some audio and ML dependencies may not yet support newer Python releases.

## Setup

Create an isolated Python environment, install the runtime dependencies, create
local configuration, and run the dependency-free dry-run smoke path:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
test -f .env || cp .env.example .env
python -m src.main --dry-run
```

Edit `.env` and replace the placeholder OpenAI key:

```text
OPENAI_API_KEY=sk-...
```

The real assistant requires the packages in `requirements.txt`, an
`OPENAI_API_KEY`, macOS microphone permission, and macOS `afplay` playback.
The runtime dependency set is `sounddevice`, `numpy`, `scipy`, `openai`,
`openwakeword`, `ai-edge-litert`, and `python-dotenv`.

Wake-word detection uses the openWakeWord Hey Jarvis TFLite model through LiteRT.
The default `.env` settings are `WAKE_BACKEND=openwakeword`,
`WAKE_MODEL=hey_jarvis`, `WAKE_INFERENCE_FRAMEWORK=tflite`, and
`WAKE_THRESHOLD=0.5`. The model files are prepared explicitly so setup failures
are visible before microphone capture starts:

```bash
python -m src.main --prepare-wake-word
```

Wake acknowledgement playback is enabled by default. Generate the short local
acknowledgement file once before starting the real assistant:

```bash
python -m src.main --prepare-acknowledgement
```

The complete deployment sequence is documented in [DEPLOYMENT.md](DEPLOYMENT.md).

To inspect local runtime readiness without starting the assistant, run:

```bash
python -m src.main --diagnose
```

For the dependency-free full-loop smoke path, run:

```bash
python -m src.main --fake-backend
```

To inspect local structured tool routing for typed text without microphone,
wake-word detection, OpenAI, TTS, playback, or network access, run:

```bash
python -m src.main --text "现在几点"
```

Weather text-debug requests such as `python -m src.main --text "明天天气怎么样"`
use the configured Open-Meteo provider and require network access.

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

Before the real demo, follow [DEPLOYMENT.md](DEPLOYMENT.md): install
requirements, set `OPENAI_API_KEY`, run `python -m src.main
--prepare-wake-word`, run `python -m src.main --prepare-acknowledgement`, run
`python -m src.main --diagnose`, and fix any reported errors. Grant macOS
microphone permission to the terminal or agent surface that launches the
assistant.

Start the assistant:

```bash
python -m src.main
```

Say `Hey Jarvis`, wait for the short acknowledgement such as `在呢`, then ask
`what is two plus two?`. The app drains acknowledgement speaker residue before
recording the question, transcribes it, answers through the local calculator
tool, writes `tmp/output.mp3`, plays it through `afplay`, and returns to
`WAIT_WAKE` for the next wake phrase.

The accepted first MVP wake phrase is `Hey Jarvis`; custom wake-word model
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
WAKE_PHRASE=hey jarvis
WAKE_BACKEND=openwakeword
WAKE_MODEL=hey_jarvis
WAKE_INFERENCE_FRAMEWORK=tflite
WAKE_THRESHOLD=0.5
WAKE_ACKNOWLEDGEMENT_ENABLED=1
WAKE_ACKNOWLEDGEMENT_TEXT=在呢
WAKE_ACKNOWLEDGEMENT_AUDIO_PATH=tmp/ack.mp3
WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS=0.35
POST_PLAYBACK_WAKE_COOLDOWN_SECONDS=1.0
POST_PLAYBACK_QUIET_SECONDS=0.5
POST_PLAYBACK_QUIET_RMS=500
POST_PLAYBACK_MAX_SUPPRESSION_SECONDS=6.0
WAKE_CONFIRMATION_FRAMES=2
SILENCE_SECONDS=1.5
MAX_RECORD_SECONDS=20
SAMPLE_RATE=16000
TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
CHAT_MODEL=gpt-4o-mini
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=alloy
TTS_INSTRUCTIONS=
TTS_SPEED=1.0
ENABLE_TOOLS=1
TOOL_ROUTER_DEBUG=0
WEATHER_PROVIDER=open-meteo
FX_PROVIDER=frankfurter
STOCK_PROVIDER=finnhub
TOOL_HTTP_TIMEOUT_SECONDS=5
DEFAULT_LOCATION=Singapore
DEFAULT_BASE_CURRENCY=USD
FINNHUB_API_KEY=
WAKE_DEBUG=0
```

`TTS_INSTRUCTIONS` maps OpenAI.fm-style vibe text to the speech API's
instructions field, for example `Speak warmly, quickly, and with dry humor`.
There is no separate OpenAI.fm vibe parameter in this assistant. `TTS_SPEED`
sets generated-audio speed and must stay between `0.25` and `4.0`; `1.0` keeps
the API default behavior.

`WAKE_ACKNOWLEDGEMENT_TEXT` controls the short phrase generated by `python -m
src.main --prepare-acknowledgement`, defaulting to `在呢`.
`WAKE_ACKNOWLEDGEMENT_AUDIO_PATH` points to the prepared local MP3, defaulting to
`tmp/ack.mp3`. Normal wake handling reuses that file and does not make a fresh
TTS request for every wake event. `WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS` controls
how long microphone residue is discarded after acknowledgement playback before
the normal recorder starts.

## Structured Tool Routing

`ENABLE_TOOLS=1` enables a deterministic routing boundary after transcription
and before chat generation. `TOOL_ROUTER_DEBUG=1` logs the selected route, tool,
params, and rule reason during the voice loop. Local time requests and simple
arithmetic are answered without asking the chat model. Weather requests are
answered through Open-Meteo when `WEATHER_PROVIDER=open-meteo`. Stock and FX
requests still return clear provider-not-configured answers until their
provider-specific follow-up features land. Unsupported realtime-sensitive requests such as
`今天有什么新闻` are refused instead of falling back to chat memory or model
guessing.

`WEATHER_PROVIDER=open-meteo` resolves city names through Open-Meteo geocoding
and fetches current, today, or tomorrow weather from Open-Meteo forecast data.
`DEFAULT_LOCATION=Singapore` is used when the user asks a weather question
without naming a place. Weather answers include source, location, observation or
forecast time, temperature, feels-like or weather-code context, and rain or
precipitation probability where Open-Meteo provides it. `FX_PROVIDER=frankfurter`
and `STOCK_PROVIDER=finnhub` name planned providers for later features.
`TOOL_HTTP_TIMEOUT_SECONDS=5` is the shared JSON request timeout.
`DEFAULT_BASE_CURRENCY=USD` is the default future FX base currency.
`FINNHUB_API_KEY` is optional until stock quotes are enabled; diagnostics and
text debug report it as configured or missing without printing the secret value.

Use the text debug path to inspect the route, params, tool result summary, and
final answer plus provider configuration:

```bash
python -m src.main --text "2 + 2"
python -m src.main --text "明天天气怎么样"
python -m src.main --text "weather in Tokyo today"
python -m src.main --text "苹果怎么样"
python -m src.main --text "今天有什么新闻"
```

Structured tools do not browse the web during automated tests; weather provider
tests mock Open-Meteo geocoding and forecast responses through the shared JSON
HTTP boundary. F022 supports local time, safe local calculator expressions,
conservative route detection for provider-backed weather, stock, and FX
requests, and refusal for unsupported realtime categories such as news, sports
scores, product prices, or arbitrary live web facts. F023 adds the shared
provider configuration and mocked JSON HTTP boundary. F024 enables Open-Meteo
weather. Manual real-provider smoke expectations for FX and stock begin with
F025 and F026.

The automated recovery check uses fakes and dry-run paths, so it does not make
live OpenAI API calls or live provider network calls.

## Wake-Word Debugging

Use `python -m src.main --wake-debug` when the assistant remains in `WAIT_WAKE`
and you need to see live microphone levels and wake-word scores without making
OpenAI requests or playing audio. Debug output includes the requested wake
model, selected inference framework, loaded model keys, `rms`, `peak`,
`overflow`, `score`, `threshold`, and `detected`. Scores are printed with enough
precision to tell true zeros from tiny non-zero model outputs, followed by a
summary with the frame count, maximum observed score, per-key maximum scores,
threshold, and detected frame count.

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

For lower-level openWakeWord comparison, `scripts/debug_oww_file.py` accepts an
optional wake model and inference framework:

```bash
python scripts/debug_oww_file.py tmp/wake-debug.wav hey_jarvis tflite
```

The script prints the requested model, selected inference framework, loaded
model keys, and per-key maximum scores.

Set `WAKE_DEBUG=1` in `.env` to log the same wake-word score fields during
normal `WAIT_WAKE` listening.

Common outcomes:

- `rms` and `peak` stay near `0`: the app is receiving silence; check macOS
  microphone permission, input device selection, and physical input level.
- `overflow=true`: microphone capture or wake-word processing fell behind; close
  CPU-heavy processes and confirm the wake-word model is prepared before
  listening.
- `score` rises but stays below `threshold`: lower `WAKE_THRESHOLD` cautiously or
  speak the accepted `Hey Jarvis` phrase more clearly.
- `score` stays low while `rms` and `peak` move: the microphone is working, but
  openWakeWord is not matching the phrase; check pronunciation, distance, and
  background noise.
- The assistant wakes immediately after playback when nobody spoke: keep
  `POST_PLAYBACK_WAKE_COOLDOWN_SECONDS` above `0`, keep
  `POST_PLAYBACK_QUIET_SECONDS` above `0`, keep `WAKE_CONFIRMATION_FRAMES` at
  `2` or higher, and rerun the playback-overlap manual test.

## Troubleshooting

- `OPENAI_API_KEY is required`: copy `.env.example` to `.env` and replace the
  placeholder value.
- `OpenAI transcription returned empty text`: the assistant did not get usable
  speech from the recorded question. It logs the recoverable error and returns
  to `WAIT_WAKE`; try again closer to the microphone or reduce background noise.
- `sounddevice is not importable`, `openai is not importable`, or another
  dependency is missing: activate `.venv` and run `pip install -r
  requirements.txt`.
- `wake_word_models` reports missing files: activate `.venv` and run `python -m
  src.main --prepare-wake-word`, then run `python -m src.main --diagnose` again.
- `wake_acknowledgement_audio` reports a missing file: activate `.venv`, set
  `OPENAI_API_KEY`, run `python -m src.main --prepare-acknowledgement`, then run
  `python -m src.main --diagnose` again.
- `LiteRT/TFLite runtime is not importable`: activate `.venv` and run `pip
  install -r requirements.txt`; the MVP wake-word path uses TFLite models.
- `WAKE_INFERENCE_FRAMEWORK=onnx` on macOS ARM64: use
  `WAKE_INFERENCE_FRAMEWORK=tflite`. Local debugging and upstream issue evidence
  showed near-zero openWakeWord scores with ONNX on Apple Silicon while
  TFLite produced usable scores.
- `onnxruntime is not importable`: this only applies if you explicitly choose
  `WAKE_INFERENCE_FRAMEWORK=onnx`; install `onnxruntime` separately and do not
  use ONNX on macOS ARM64.
- Microphone capture fails or records silence: confirm the launching terminal has
  macOS microphone permission, then restart that terminal.
- Microphone input overflows while the app is in `WAIT_WAKE`: the wake-word
  model may still be starting up or audio processing may have fallen behind.
  Run `python -m src.main --prepare-wake-word`, restart the app, and close other
  CPU-heavy audio or ML processes before trying the wake phrase again.
- Playback fails: run `python -m src.main --diagnose` and confirm `afplay` is
  available. The MVP is macOS-only for playback.
- Playback finishes and immediately triggers a new wake event: the app now
  discards a short post-playback microphone window, waits for observed quiet,
  and requires consecutive wake-positive frames. Increase
  `POST_PLAYBACK_WAKE_COOLDOWN_SECONDS` or `POST_PLAYBACK_QUIET_SECONDS` if room
  echo or speaker bleed still retriggers wake detection.
- Wake-word detection does not trigger: use the accepted phrase `Hey Jarvis`,
  speak clearly near the microphone, confirm the app is still in `WAIT_WAKE`,
  then run `python -m src.main --wake-debug` or set `WAKE_DEBUG=1` to inspect
  microphone levels and wake scores.

## Recovery Check

From the repository root:

```bash
./init.sh
```

The recovery check runs the AI Agent Harness verification, compiles project Python files, runs tests, and executes dry-run plus fake-backend smoke paths.

Use [DEPLOYMENT.md](DEPLOYMENT.md) for live macOS deployment and wake-word
acceptance testing after the recovery check passes.

## Post-MVP TODOs

- Interrupt playback when the user says `Hey Jarvis` while audio is still
  playing.
- Keep listening for a six-second follow-up question after each answer before
  returning to wake-word-only mode.
- Add configurable custom wake-word model loading instead of only using the
  built-in openWakeWord Hey Jarvis model.

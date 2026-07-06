# Deployment

Hey Jarvis is deployed as a local macOS Python process. It is not a server
deployment: the runtime needs the local microphone, the local speaker path
through `afplay`, OpenAI credentials, and the openWakeWord Hey Jarvis TFLite model
files on the same machine that launches the assistant.

## Supported Target

- macOS with microphone access for the launching terminal or agent surface.
- Python 3.11 or Python 3.12.
- `afplay` available on `PATH`.
- Network access during setup for Python packages and wake-word model downloads.
- A valid `OPENAI_API_KEY` for real transcription, chat, and text-to-speech.

The active wake-word path is openWakeWord's built-in Hey Jarvis model with TFLite:

```text
WAKE_BACKEND=openwakeword
WAKE_MODEL=hey_jarvis
WAKE_INFERENCE_FRAMEWORK=tflite
WAKE_PHRASE=hey jarvis
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
```

Manual acceptance cases are tracked in [MANUAL_TESTING.md](MANUAL_TESTING.md).

On macOS ARM64, do not deploy with `WAKE_INFERENCE_FRAMEWORK=onnx`; the project
intentionally uses TFLite there because local debugging found ONNX wake-word
scores collapsed near zero while TFLite produced usable scores.

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

The default OpenAI speech settings preserve the normal generated voice:

```text
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=alloy
TTS_INSTRUCTIONS=
TTS_SPEED=1.0
```

Use `TTS_INSTRUCTIONS` for OpenAI.fm-style vibe text such as `Speak warmly,
quickly, and with dry humor`; the assistant sends that value as speech API
instructions rather than using a separate OpenAI.fm vibe parameter. `TTS_SPEED`
controls generated-audio speed and must be from `0.25` through `4.0`.

Structured local tools are enabled by default:

```text
ENABLE_TOOLS=1
TOOL_ROUTER_DEBUG=0
WEATHER_PROVIDER=open-meteo
FX_PROVIDER=frankfurter
STOCK_PROVIDER=finnhub
TOOL_HTTP_TIMEOUT_SECONDS=5
DEFAULT_LOCATION=Singapore
DEFAULT_BASE_CURRENCY=USD
FINNHUB_API_KEY=
```

`ENABLE_TOOLS` routes local time and simple calculator requests before chat
generation. Weather requests use Open-Meteo when `WEATHER_PROVIDER=open-meteo`.
FX requests use Frankfurter reference rates when `FX_PROVIDER=frankfurter`.
Stock requests use Finnhub when `STOCK_PROVIDER=finnhub` and a real
`FINNHUB_API_KEY` is configured.
`TOOL_ROUTER_DEBUG=1` logs route, tool, params, and rule reason during the voice
loop.

`WEATHER_PROVIDER=open-meteo` resolves city names through Open-Meteo geocoding
and fetches current, today, or tomorrow weather from the Open-Meteo forecast
endpoint. `TOOL_HTTP_TIMEOUT_SECONDS` is the shared JSON request timeout.
`DEFAULT_LOCATION=Singapore` is used when the user omits a weather location.
`DEFAULT_BASE_CURRENCY=USD` is used when an FX request omits the base currency;
when the quote is omitted, the configured default base is used as the quote
unless that would match the base, in which case SGD is used. Frankfurter FX
answers are reference rates, not bank cash rates or executable trade quotes.
`FINNHUB_API_KEY` is required for Finnhub stock quotes. Diagnostics report
configured or missing without printing the value. Stock quote answers include
current price, change, percent change, day high and low, open, previous close,
the Finnhub quote timestamp, plus caveats that market data may be delayed and
the result is not trading advice.

Wake acknowledgement playback is enabled by default. The assistant plays the
prepared `WAKE_ACKNOWLEDGEMENT_AUDIO_PATH` file after `Hey Jarvis`, drains
microphone residue for `WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS`, and then records
the user's question. Normal wake handling reuses the local acknowledgement file
and does not call TTS on every wake event.

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

This prepares the Hey Jarvis model plus the required feature models. Re-run the
command after changing `WAKE_MODEL` or `WAKE_INFERENCE_FRAMEWORK`.

## Prepare Wake Acknowledgement

Generate the configured local acknowledgement audio before starting the real
assistant:

```bash
python -m src.main --prepare-acknowledgement
```

This writes `WAKE_ACKNOWLEDGEMENT_TEXT`, default `在呢`, to
`WAKE_ACKNOWLEDGEMENT_AUDIO_PATH`, default `tmp/ack.mp3`, through the configured
OpenAI TTS boundary.

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
wake-word model files, missing `wake_acknowledgement_audio`, or microphone
permission not yet granted to the launching app.

For an end-to-end state-machine smoke test without hardware or OpenAI:

```bash
python -m src.main --fake-backend
```

For local structured tool routing without microphone, wake-word detection, TTS,
playback, OpenAI, or external network access:

```bash
python -m src.main --text "现在几点"
python -m src.main --text "100加20是多少"
python -m src.main --text "今天有什么新闻"
```

For a manual Open-Meteo weather smoke with live network access, run:

```bash
python -m src.main --text "明天天气怎么样"
python -m src.main --text "weather in Tokyo today"
```

For a manual Frankfurter FX smoke with live network access, run:

```bash
python -m src.main --text "100 USD to SGD"
python -m src.main --text "100美元兑人民币汇率是多少"
```

For a manual Finnhub stock smoke with live network access and
`FINNHUB_API_KEY` set, run:

```bash
python -m src.main --text "AAPL stock price"
python -m src.main --text "苹果股价多少"
```

Automated tests mock the shared JSON HTTP boundary and must not call live
weather, FX, or stock services.

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

Say `Hey Jarvis` clearly near the microphone. Stop the command with `Ctrl-C`, then
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
Hey Jarvis
```

After the acknowledgement plays, ask:

```text
what is two plus two?
```

The assistant should drain acknowledgement audio residue, record the question to
`tmp/input.wav`, transcribe it, ask the configured chat model, write speech to
`tmp/output.mp3`, play it with `afplay`, and return to `WAIT_WAKE`.

Stop the process with `Ctrl-C`.

## Update Or Redeploy

After pulling new code:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --prepare-wake-word
python -m src.main --prepare-acknowledgement
./init.sh
python -m src.main --diagnose
```

Only start the real assistant after recovery and diagnostics pass.

## Runtime Files

- `.env`: local secrets and runtime settings. Do not commit it.
- `.env.example`: documented deployable defaults.
- `tmp/input.wav`: latest normal question recording.
- `tmp/output.mp3`: latest synthesized answer.
- `tmp/ack.mp3`: prepared wake acknowledgement audio.
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
- `wake_acknowledgement_audio` reports a missing file: set `OPENAI_API_KEY`,
  run `python -m src.main --prepare-acknowledgement`, then run `python -m
  src.main --diagnose` again.
- `WAKE_INFERENCE_FRAMEWORK=onnx` fails on macOS ARM64: keep
  `WAKE_INFERENCE_FRAMEWORK=tflite`.
- `rms` and `peak` stay near zero during `--wake-debug`: grant microphone
  permission, choose the correct input device, and restart the launching app.
- `overflow=true`: close CPU-heavy processes and make sure wake-word models were
  prepared before listening.
- Playback fails: run `python -m src.main --diagnose` and confirm `afplay` is
  available.
- `FINNHUB_API_KEY` is reported as missing: set a real Finnhub key in `.env`
  before asking stock quote questions. Diagnostics and text debug never print
  the key value.
- Stock quote requests for unknown symbols, zero current prices, provider
  failures, or malformed Finnhub responses return structured tool errors and do
  not fall back to chat speculation.
- Playback finishes and immediately wakes again: keep
  `POST_PLAYBACK_WAKE_COOLDOWN_SECONDS` enabled, keep
  `POST_PLAYBACK_QUIET_SECONDS` enabled, keep `WAKE_CONFIRMATION_FRAMES` at `2`
  or higher, and increase the cooldown or quiet window if speaker echo still
  bleeds into the microphone.

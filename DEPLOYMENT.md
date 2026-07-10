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
WAKE_ACKNOWLEDGEMENT_AUDIO_PATH=var/ack.mp3
WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS=0.35
POST_PLAYBACK_WAKE_COOLDOWN_SECONDS=1.0
POST_PLAYBACK_QUIET_SECONDS=0.5
POST_PLAYBACK_QUIET_RMS=500
POST_PLAYBACK_MAX_SUPPRESSION_SECONDS=6.0
WAKE_CONFIRMATION_FRAMES=2
ARMED_NO_SPEECH_TIMEOUT_SECONDS=2.0
ARMED_VOICE_RMS=750
ARMED_MIN_RMS=750
ARMED_SNR_MULTIPLIER=2.5
ARMED_VOICE_WINDOW_SECONDS=0.30
ARMED_VOICE_REQUIRED_RATIO=0.75
ARMED_CLIP_REJECT_PEAK=32000
ARMED_PRE_ROLL_SECONDS=0.50
MIN_VALID_SPEECH_SECONDS=0.50
MIN_TRANSCRIPT_LENGTH=2
CANCEL_PHRASES=取消,没事,不用了,算了,stop,cancel,never mind
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
TOOL_ANSWER_NATURALIZATION=1
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
`TOOL_ANSWER_NATURALIZATION=1` sends only successful Open-Meteo weather,
Frankfurter FX, and Finnhub stock `ToolResult` values through a separate OpenAI
wording pass that must preserve numbers, units, timestamps, sources, caveats,
and advice disclaimers. Raw provider data remains authoritative; failures, missing
credentials, realtime refusals, calculator/local-time answers, empty
naturalization output, and recoverable OpenAI errors keep the deterministic raw
answer and do not fall back to chat speculation. Text debug reports the raw
answer and `naturalization_status` without calling OpenAI or printing secrets.

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
microphone residue for `WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS`, enters `ARMED`,
and records only after a recent window contains enough speech-like chunks above
the adaptive threshold `max(ARMED_MIN_RMS, noise_floor *
ARMED_SNR_MULTIPLIER)`. ARMED rejects overflowed and clipped chunks, preserves
`ARMED_PRE_ROLL_SECONDS` of recent audio before recording, and logs
`armed_summary` or `armed_trigger` with RMS, peak, overflow, noise-floor,
threshold, voiced-window, and pre-roll context. If no speech arrives within
`ARMED_NO_SPEECH_TIMEOUT_SECONDS`, or the transcript is empty, filler, too
short, or a configured `CANCEL_PHRASES` entry, the assistant returns to
`WAIT_WAKE` without chat/tool routing, answer TTS, playback, or chat-history
changes. Cancel matching also accepts conservative short noisy suffixes such
as `没事了`, `没事不用了`, `没事 谢谢`, `没事 后面有声音`, `取消吧`, and
`算了算了`, plus colloquial spoken variants such as `不用啦`, `不用不用`,
`不用不用了`, `不要了`, `没事儿`, and `没事没事儿`, while command-like
continuations such as `不用了帮我查天气`, `没事的话帮我查天气`,
`取消我明天的闹钟`, `不要取消我明天的闹钟`, or `cancel my alarm tomorrow`
continue to chat/tool routing. Transcript-cancel logs include the normalized
transcript and `match_mode`; short non-cancel transcripts log safe
`match_decision=not_cancelled` diagnostic context.
After any local cancellation, including no speech after acknowledgement or a
cancel transcript such as `算了算了`, the assistant suppresses wake detection
with the same cooldown and observed-quiet settings used after answer playback.
The cancellation path logs the reason, discarded chunk counts, quiet-gate
status, and maximum suppressed wake score before it becomes wake-ready again.
Normal wake handling reuses the local acknowledgement file and does not call
TTS on every wake event.

Question recording stops on `SILENCE_SECONDS` of recent-window audio mostly
below `RECORDING_SILENCE_RMS`, default `750`, or on the `MAX_RECORD_SECONDS`
safety cap. This keeps normal 4-5 second utterances from waiting for the full
20 second maximum when the room has steady low or moderate background noise,
while speech-like chunks still extend recording. Recording logs preserve
`stopped_by=silence` and `stopped_by=max_duration` without logging raw audio.

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
`WAKE_ACKNOWLEDGEMENT_AUDIO_PATH`, default `var/ack.mp3`, through the configured
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
`tmp/input.wav` after `ARMED` detects speech, transcribe it, ask the configured
chat model or structured tool route, write speech to `tmp/output.mp3`, play it
with `afplay`, and return to `WAIT_WAKE`.

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
- `var/ack.mp3`: prepared wake acknowledgement audio.
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
- Wake acknowledgement plays but no question is intended: keep
  `ARMED_NO_SPEECH_TIMEOUT_SECONDS` enabled so the assistant cancels locally
  before recording, transcription, answer generation, or TTS playback.
- Wake acknowledgement repeats after a local cancellation: keep
  `POST_PLAYBACK_WAKE_COOLDOWN_SECONDS` and `POST_PLAYBACK_QUIET_SECONDS`
  enabled. Cancellation should log post-cancellation suppression and should not
  enter another acknowledgement cycle until fresh wake audio arrives after quiet.

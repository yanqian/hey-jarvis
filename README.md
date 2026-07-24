# Hey Jarvis

Hey Jarvis is a simple macOS voice assistant MVP.

The accepted first demo flow is:

```text
User: "Hey Jarvis, what is two plus two?"
Assistant: "The answer is 4."
```

## Status

This project now includes the MVP voice-assistant loop behind testable boundaries. The recovery entrypoint proves the Python package, tests, and a fake-backend state-machine path work without requiring a microphone, speakers, or OpenAI credentials. Real audio capture, wake-word detection, OpenAI transcription/chat/TTS, and macOS playback are wired through `python -m src.main`.

The existing pipeline remains the default backend. `BACKEND=realtime` or `--backend realtime` opts into the Realtime WebRTC path. Run `python -m src.main --backend realtime`, click **Arm hands-free audio** once in the launched Chrome app, then say the configured wake phrase. Confirmed local wake closes Python capture, plays the local acknowledgement, and hands exclusive microphone/playback ownership to a continuous WebRTC session; follow-up turns and server-managed interruption do not require another wake. Idle, maximum-duration, explicit-stop, transport-error, and Ctrl+C cleanup stop browser media before returning to fresh local wake listening. Realtime defaults use `gpt-realtime-2.1`, voice `marin`, direct browser output gain `0.1`, 15-second idle and 600-second maximum duration, server VAD, input transcription, a local acknowledgement, bounded debug events, conservative bilingual end phrases, and `127.0.0.1:8770`. Run `python -m src.main --backend realtime --diagnose` to inspect host assets, model/voice/output gain, credential, loopback, and exclusive audio-handoff readiness. The standard API key stays in Python and is never transported through the bridge.

Arming is a one-time action for each Chrome app launch, not each conversation.
Chrome owns its microphone permission for that host lifetime; macOS or Chrome
may ask again after permission is revoked, the app profile changes, or the host
is relaunched. Before a local wake, only the Python wake detector holds the
microphone: no pre-wake PCM, transcript, or wake audio is uploaded to OpenAI.
After handoff, WebRTC sends session audio directly to Realtime and plays its
returned audio directly. Realtime audio and optional input transcription are
billable API usage; check the current OpenAI pricing for the selected model.
This remains an opt-in developer MVP: signing, notarization, a bundled browser
host, launch-at-login, and distributable `.app` packaging are deferred.

Default `/api/report` and application logs retain at most bounded sanitized
lifecycle events. They exclude API keys, ephemeral credentials, raw/base64
audio, audio deltas, tool arguments/results, call ids, and transcript text.
`REALTIME_DEBUG=1` enables additional browser-side local troubleshooting events,
but the browser list is still bounded and content fields remain summarized; do
not publish debug output without reviewing it.

`REALTIME_END_PHRASES` closes an active session only when a completed input
transcription is an exact short utterance after case, outer punctuation, and
whitespace normalization. For example, `再见。` and `GOODBYE!` match defaults,
while `再见北京`, `please say goodbye`, partial events, ordinary
`CANCEL_PHRASES`, and duplicate item events do not. A match enters the same
bounded media-closing path as explicit stop; default logs record only the
outcome, never transcript text. Set `REALTIME_INPUT_TRANSCRIPTION_ENABLED=0`
to disable this optional control signal; idle, maximum duration, explicit stop,
and transport-error exits continue to work.

OpenAI documents that Realtime input transcription runs asynchronously from
response creation, may arrive before or after response events, uses a separate
ASR model, can diverge from the Realtime model's interpretation, and should be
treated only as a rough guide. Its usage is billed according to the selected
ASR model rather than the Realtime model. This project therefore uses it only
for conservative exact end-phrase control, not for conversation meaning. See
the [official completed-transcription event reference](https://developers.openai.com/api/reference/resources/realtime/server-events#conversation.item.input_audio_transcription.completed)
for current behavior and pricing semantics.

Realtime advertises exactly two local functions: `calculator` and
`end_conversation`. Completed function arguments are correlated to their active
call, bounded and de-duplicated in Python. Calculator calls execute through the
same existing `safe_calculator` used by the pipeline; the host returns one
`function_call_output` and asks the same Realtime conversation to continue
speaking the answer. A clear, unambiguous request to leave or say goodbye calls
`end_conversation` with an empty object, produces no tool output or substantive
spoken reply, and enters the existing bounded media-cleanup path. This semantic
close does not depend on the rough-guide transcription; exact configured
completed-transcription phrases remain a conservative fallback. Mentions,
quotations, translations, or requests to say farewell are not close commands.
Weather, FX, stocks, provider credentials, shell access, arbitrary routing, and
pipeline chat-history mutation are intentionally outside this MVP tool boundary.
Malformed or unsafe calculator expressions receive a bounded error and are never
executed with `eval`; malformed end calls fail closed without ending the session.
This follows the [official Realtime function-calling flow](https://developers.openai.com/api/docs/guides/realtime-conversations#function-calling): configure session tools, return a correlated `function_call_output`, then request the continuation response.

```text
BACKEND=pipeline
REALTIME_MODEL=gpt-realtime-2.1
REALTIME_VOICE=marin
REALTIME_OUTPUT_VOLUME=0.1
REALTIME_IDLE_TIMEOUT_SECONDS=15
REALTIME_MAX_DURATION_SECONDS=600
REALTIME_SERVER_VAD_ENABLED=1
REALTIME_SERVER_VAD_THRESHOLD=0.8
REALTIME_INPUT_TRANSCRIPTION_ENABLED=1
REALTIME_ACKNOWLEDGEMENT_MODE=local
REALTIME_DEBUG=0
REALTIME_END_PHRASES=结束对话,再见,goodbye,end conversation
REALTIME_BRIDGE_HOST=127.0.0.1
REALTIME_BRIDGE_PORT=8770
```

`REALTIME_OUTPUT_VOLUME` is the browser `<audio>` playback gain, from `0.1` to
`1.0`; it does not re-encode or route returned audio through Python. The `0.1`
default passed five consecutive built-in-speaker cycles with no unexpected
speech starts while preserving deliberate barge-in from 15 ms through 118 ms on
the tested Mac. Higher values are louder but can reintroduce speaker echo as
false user speech; tune against M057 rather than assuming one value is universal.

`REALTIME_SERVER_VAD_THRESHOLD` is the official server-VAD activation threshold
from `0.0` through `1.0`. The quiet speakerphone profile defaults to `0.8` so
residual speaker echo must be louder before it can interrupt; M057 must still
prove that deliberate speech triggers promptly at the chosen microphone distance.

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

The opt-in Realtime controller has a deterministic full-lifecycle smoke covering
wake, exclusive handoff, connection, two turns, assistant completion,
interruption, calculator output, end phrase, close, and return to `WAIT_WAKE`.
It transports no PCM and opens no microphone, browser, speaker, network, OpenAI
connection, or wall-clock sleep:

```bash
python -m src.realtime.fake_smoke
```

For repeatable local acceptance, record private voice fixtures with
`python -m src.realtime.fixtures record wake --seconds 4` (and the names
`turn-1`, `turn-2`, or `barge-in`). Files and a transcript-free integrity
manifest persist under `tmp/realtime-fixtures/`, which is excluded from Git.
`python -m src.realtime.fixtures list` reports only duration and capture health.
Use `python -m src.realtime.fixtures trim NAME --start SECONDS --end SECONDS`
to preserve the original while creating a shorter private `replay/` derivative;
the event-driven runner prefers that derivative when present.
Same-Mac speaker replay is useful for orchestration but may correctly be removed
by browser echo cancellation, so final no-headphones barge-in acceptance still
uses one real near-end spoken interruption.
After launching and arming the Realtime host, run
`python -m src.realtime.fixture_runner` for event-driven acoustic replay. The
runner advances only on sanitized lifecycle events and requests a safe stop on
failure; it never reads transcripts or sends PCM through the Python bridge.

The spec-driven Realtime suite starts with `RT001`, the automatic
saved-wake-to-connected ownership check. Its versioned contract is
`evals/realtime/scenarios/RT001.json`. Once the Realtime backend is launched,
the browser host has been armed once, and the private `wake` fixture exists,
run:

```bash
python -m src.evals.realtime_handoff live
```

RT001 needs no fresh human speech: it replays the saved wake, proves the Python
wake microphone closes before browser microphone request/acquisition and
`host_connected`, explicitly stops the session, and proves wake ownership is
restored. The command still opens the real microphone, connects to OpenAI, and
can incur Realtime charges, so each live-host run requires explicit
authorization. It writes only bounded lifecycle metadata to
`tmp/realtime-evals/RT001-evidence.json`; audio, transcripts, credentials, SDP,
provider bodies, and tool content are excluded. The same oracle can evaluate a
saved sanitized observation with no live resources:

```bash
python -m src.evals.realtime_handoff offline path/to/observation.json
```

`RT002` extends that automatic pattern to two continuous turns. Record the
private `turn-1` and `turn-2` fixtures once. Routine runs require no fresh speech:

```bash
python -m src.evals.realtime_two_turn live
```

The runner verifies each selected WAV against its local Git-ignored manifest,
plays wake acoustically, injects both saved turns through the active WebRTC data
channel after browser echo cancellation as two atomic audio conversation items,
waits for exactly two ordered completed responses under one connection/session
identity, then stops and
restores wake ownership. Post-AEC injection keeps routine replay deterministic
without disabling the product's real microphone processing.
It evaluates lifecycle continuity only, not transcript or answer semantics.
The live fixture-replay run still requires explicit microphone/OpenAI/cost
authorization. Offline sanitized observations use:

```bash
python -m src.evals.realtime_two_turn offline path/to/observation.json
```

`RT004` automatically proves that close and next-wake recovery work twice under
one browser Arm lease. It replays the saved private wake, connects session A,
uses the existing explicit stop, requires browser stop before Python wake
microphone reopen, then replays the same wake to connect a distinct session B
and performs the same bounded cleanup:

```bash
python -m src.evals.realtime_close_recovery live
python -m src.evals.realtime_close_recovery offline path/to/observation.json
```

Routine RT004 runs require no fresh speech and do not ask or judge a user
question. The live-host command still opens the built-in microphone, connects
to OpenAI twice, and may incur Realtime charges, so every execution requires
fresh explicit microphone/OpenAI/cost authorization. Evidence contains only
bounded lifecycle metadata; private wake audio and content remain Git-ignored.

`RT003` covers deliberate near-end interruption during a long answer. Its
versioned contract is
`evals/realtime/scenarios/RT003.json`. Offline evaluator tests apply the same
oracle to sanitized reports without devices or network. For the required live
evidence, launch the Realtime backend, click **Arm hands-free audio** once, keep
the built-in microphone and speaker active without headphones, and run:

```bash
python -m src.evals.realtime_barge_in live
```

The command uses the private local `wake` fixture to enter the session, then
waits at one fail-closed pre-session readiness gate. Press Enter once when
ready; only then does it play the wake fixture, establish the Realtime session,
and promptly send the long-answer request so operator delay cannot consume the
session's idle timeout. After the exact `response.created` marker, it
immediately tells the prepared operator to wait until counting is audible and
speak one natural interruption utterance. That one utterance is both the
audible-answer confirmation and the only scenario speech action; no second
terminal/chat round trip can let the active answer expire. Type `cancel`, `q`,
or `quit` at the readiness gate to stop safely. It passes only when the old answer
ends as `cancelled` within 1000ms, the continuation completes, and cleanup
restores `wake_owned` with the local wake microphone open. If input closes,
confirmation is cancelled, the answer or session ends before speech, speech is
not detected, an oracle fails, or cleanup is incomplete, the command exits non-zero
but still requests bounded cleanup and saves a precise sanitized FAIL result; a
product failure is never relabeled as a passing eval. Evidence defaults to
`tmp/realtime-evals/RT003-evidence.json` and contains only allowlisted sanitized
event fields. It never stores transcript text, raw/base64 audio, tool payloads,
or credentials. Real near-end speech is mandatory: same-Mac fixture replay may
be removed by browser echo cancellation and does not prove human barge-in.

To re-evaluate a saved sanitized observation without live resources:

```bash
python -m src.evals.realtime_barge_in offline path/to/observation.json
```

If RT003 reports no `host_speech_started`, run the diagnosis-only F060 workflow
before changing Realtime settings:

```bash
python -m src.evals.realtime_input_diagnosis live
```

The command uses the same private wake fixture and exact browser microphone
MediaStream sent to WebRTC. It first measures a short silence baseline, asks for
one normal utterance with no remote answer playing, then starts the counting
answer and asks for one utterance during playback. The browser retains no sample
arrays or waveform: it sends only bounded 500 ms normalized, rounded RMS/peak
windows labeled `no_remote_playback` or `remote_playback`. The result is one of
`capture_path`, `server_vad_sensitivity`, `full_duplex_attenuation`,
`event_orchestration`, or `inconclusive`, with supporting summary metrics.

F060 is diagnostic evidence, not automatic tuning and not an RT003 pass. It
does not change `REALTIME_SERVER_VAD_THRESHOLD`, `REALTIME_OUTPUT_VOLUME`,
microphone constraints, echo cancellation, noise suppression, or automatic
gain control. Its live run uses microphone audio, sends the two test utterances
to OpenAI, and incurs Realtime audio plus optional transcription charges.
Evidence defaults to `tmp/realtime-evals/F060-diagnosis.json` and excludes raw
or base64 audio, sample arrays, transcript text, utterance text, credentials,
and tool payloads. Saved sanitized observations can be classified offline:

```bash
python -m src.evals.realtime_input_diagnosis offline path/to/observation.json
```

If WebRTC negotiation fails before the session connects, F060 retains only a
strict diagnostic allowlist: HTTP status, OpenAI `error.type` and `error.code`,
`x-request-id`, `retry-after`, and available rate-limit remaining/reset headers.
It never retains the full provider response body, SDP offer/answer, authorization
header, ephemeral secret, API key, audio, or transcript. This distinguishes
request-rate failures from quota failures when OpenAI exposes the corresponding
safe fields.

To inspect local structured tool routing for typed text without microphone,
wake-word detection, OpenAI, TTS, playback, or network access, run:

```bash
python -m src.main --text "现在几点"
python -m src.main --text "一加一等于几"
```

Weather text-debug requests such as `python -m src.main --text "明天天气怎么样"`
and FX text-debug requests such as `python -m src.main --text "100 USD to SGD"`
use configured providers and require network access.

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
`what is two plus two?` or `一百乘以一千等于多少`. Spoken Chinese calculator
operands support conservative positional integers through one `万/萬` section.
The app drains acknowledgement speaker residue before
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
WAKE_VAD_THRESHOLD=
VAD_BACKEND=disabled
VAD_MODE=2
WAKE_ACKNOWLEDGEMENT_ENABLED=1
WAKE_ACKNOWLEDGEMENT_TEXT=在呢
WAKE_ACKNOWLEDGEMENT_AUDIO_PATH=var/ack.mp3
WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS=0.35
ACK_GUARD_ENABLED=1
ACK_GUARD_MIN_QUIET_SECONDS=0.16
ACK_GUARD_QUIET_RMS=900
ACK_GUARD_MAX_BUFFER_SECONDS=1.50
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
ARMED_BASELINE_SECONDS=0.30
ARMED_BASELINE_MIN_CHUNKS=3
ARMED_REQUIRE_BASELINE=1
ARMED_LAST_CHUNK_MUST_BE_VOICED=1
ARMED_VAD_REQUIRED_RATIO=0.50
ARMED_VAD_MIN_FRAMES=2
RECORDING_VAD_ENABLED=0
RECORDING_VAD_END_RATIO=0.25
RECORDING_VAD_SPEECH_RATIO=0.50
RECORDING_HANGOVER_SECONDS=0.30
RECORDING_END_SILENCE_SECONDS=1.5
MIN_VALID_SPEECH_SECONDS=0.50
MIN_TRANSCRIPT_LENGTH=2
CANCEL_PHRASES=取消,没事,不用了,算了,stop,cancel,never mind
SILENCE_SECONDS=1.5
MAX_RECORD_SECONDS=20
RECORDING_SILENCE_RMS=750
SAMPLE_RATE=16000
TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
CHAT_MODEL=gpt-4o-mini
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=alloy
TTS_INSTRUCTIONS=
TTS_SPEED=1.0
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
`var/ack.mp3`. Normal wake handling reuses that file and does not make a fresh
TTS request for every wake event. With `ACK_GUARD_ENABLED=1`, the assistant
suppresses acknowledgement residue until it observes
`ACK_GUARD_MIN_QUIET_SECONDS` below `ACK_GUARD_QUIET_RMS`, bounded by
`ACK_GUARD_MAX_BUFFER_SECONDS`. Clipped and overflowed chunks reset the safe
boundary and never enter recording pre-roll. If no quiet boundary appears, the
loop cancels locally as `no_speech_after_wake`; it cannot enter triggerable
ARMED with `post_ack_quiet_observed=false`. `WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS`
remains the legacy fixed drain when the guard is disabled.

On the real macOS path, acknowledgement playback is started asynchronously so
the assistant can continuously consume microphone chunks while `afplay` is
running. This prevents speaker echo from accumulating as stale input and
reduces overflow. The drain summary reports chunk, overflow, clipping, RMS,
peak, and completion metrics. A bounded safe playback tail is retained as
protected recording pre-roll, while the final chunk overlapping playback
completion is quarantined. After a successful zero-overflow drain, new
post-playback speech can trigger ARMED through its baseline, real noise-floor,
energy, rolling-voice, latest-chunk, and optional VAD gates; the buffered tail
then preserves a question that began while the configured acknowledgement was still playing.
Playback-time audio alone cannot trigger recording. With one microphone and no
acoustic echo cancellation, the question must continue beyond playback
completion; a question spoken entirely during the acknowledgement is intentionally
unsupported. Unsafe synchronization and legacy players fall back to the
existing conservative bounded quiet boundary.

`ARMED_NO_SPEECH_TIMEOUT_SECONDS` controls how long the assistant waits after
wake acknowledgement for user speech before quietly returning to `WAIT_WAKE`.
`ARMED_MIN_RMS` is the minimum local RMS threshold for that speech check;
`ARMED_VOICE_RMS` remains a legacy fallback when `ARMED_MIN_RMS` is not set.
The active threshold is `max(ARMED_MIN_RMS, noise_floor *
ARMED_SNR_MULTIPLIER)`. `ARMED_VOICE_WINDOW_SECONDS` and
`ARMED_VOICE_REQUIRED_RATIO` require sustained speech-like chunks before
recording starts, `ARMED_CLIP_REJECT_PEAK` rejects clipped spikes, and
`ARMED_PRE_ROLL_SECONDS` preserves recent audio so the beginning of the user's
utterance is not dropped. With `ARMED_REQUIRE_BASELINE=1`, recording cannot
start until at least `ARMED_BASELINE_SECONDS` and
`ARMED_BASELINE_MIN_CHUNKS` of valid ARMED audio are observed.
`ARMED_LAST_CHUNK_MUST_BE_VOICED=1` prevents a stale voiced window from
triggering after speech or noise has stopped. ARMED logs `armed_summary` on timeout and
`armed_trigger` on recording start with RMS, peak, overflow, noise-floor,
voiced-window, threshold, baseline readiness/chunks/seconds, and pre-roll
context. A default recording start must show `baseline_ready=true`.

VAD is optional and disabled by default. To enable local WebRTC classification,
install the compatible optional dependency set with
`python -m pip install -r requirements-vad.txt`, set
`VAD_BACKEND=webrtc`, and choose `VAD_MODE` from 0 through 3. ARMED then
requires both its RMS gate and `ARMED_VAD_REQUIRED_RATIO` with at least
`ARMED_VAD_MIN_FRAMES` voiced 20ms frames. Its trigger/summary logs include
`vad_ratio`, `vad_ok`, `max_vad_ratio`, and voiced-chunk context. Setting
`RECORDING_VAD_ENABLED=1` adds VAD-aware endpointing using the documented end,
speech, hangover, and end-silence settings; existing `SILENCE_SECONDS`,
`RECORDING_SILENCE_RMS`, and `MAX_RECORD_SECONDS` remain active compatibility
and safety controls. Recording endpointing is asymmetric: only speech-level RMS
plus configured VAD speech evidence extends recording, while sustained RMS at
or below `RECORDING_SILENCE_RMS` advances end silence even if WebRTC remains
falsely voiced. High-RMS/VAD-low noise is not considered quiet. The endpoint
logs `low_energy_high_vad_chunks` once per recording for real-test diagnosis.
`RECORDING_VAD_END_RATIO` is the agreement boundary for that diagnostic; a VAD
ratio above it cannot veto sustained below-threshold RMS silence.
`WAKE_VAD_THRESHOLD` is independently optional: when set,
it is forwarded to openWakeWord, and an older incompatible openWakeWord version
fails with guidance to upgrade or unset the setting.
When WebRTC VAD is configured, `python -m src.main --diagnose` imports and
constructs the configured detector and classifies a valid 20ms silence frame.
It reports an error instead of an importability false positive if the optional
wrapper, its `pkg_resources` compatibility dependency, detector construction,
or native frame classification cannot run. This installation check does not
establish real-world speech/noise accuracy. F048 passed 5/5 normal continuous
question trials with `stopped_by=silence` on the tested Python 3.12 microphone
environment. `RECORDING_VAD_ENABLED=0` remains the repository default because
default enablement is a separate product decision, not because F048 endpoint
acceptance is still pending. Deliberate pauses before ARMED triggers and
clap-like transients remain separate limitations.
Guarded ACK flows also require `noise_floor_has_samples=true` and log
`post_ack_quiet_observed`, suppressed/clipped/overflow chunk counts, and the
post-ACK maximum RMS and peak. If speaker echo still reaches `max_peak=32768`,
lower playback volume or regenerate a shorter acknowledgement such as `嗯`.
After that safe boundary, ARMED treats audio as potential user speech:
overflowed chunks are omitted individually, while clipped PCM is retained in
the bounded pre-roll because it may still contain intelligible words. Neither
type counts as voiced or updates the noise floor, and neither erases earlier
 safe user chunks.
`MIN_VALID_SPEECH_SECONDS` and `MIN_TRANSCRIPT_LENGTH` reject accidental,
silent, or unusably short requests before chat/tool routing and TTS.
`CANCEL_PHRASES` is a comma-separated local cancellation list; defaults include
`取消`, `没事`, `不用了`, `算了`, `stop`, `cancel`, and `never mind`.
Cancel matching also accepts conservative short noisy suffixes such as
`没事了`, `没事不用了`, `没事 谢谢`, `没事 后面有声音`, `取消吧`,
`算了算了`, `不用啦`, `不用不用`, `不用不用了`, `不要了`, `没事儿`,
`没事没事儿`, and `stop please`
without calling chat, tools, TTS, playback, or mutating history. Longer
command-like continuations such as `不用了帮我查天气`, `没事的话帮我查天气`,
`取消我明天的闹钟`, `不要取消我明天的闹钟`, or `cancel my alarm tomorrow`
are not locally cancelled. Transcript-cancel logs include the normalized
transcript and `match_mode` for diagnosis; short non-cancel transcripts log the
normalized transcript, compact transcript, and `match_decision=not_cancelled`.
After local cancellation, the assistant also suppresses wake detection and waits
for observed quiet before becoming wake-ready again. This uses the same
`POST_PLAYBACK_WAKE_COOLDOWN_SECONDS`, `POST_PLAYBACK_QUIET_SECONDS`,
`POST_PLAYBACK_QUIET_RMS`, and `POST_PLAYBACK_MAX_SUPPRESSION_SECONDS` settings
as post-playback suppression, and logs the cancellation reason, discarded chunk
counts, quiet-gate status, and maximum suppressed wake score.

For the most reliable manual test, say `Hey Jarvis`, wait until acknowledgement
echo settles, then ask the question. A safe run logs
`post_ack_quiet_observed=true` before ARMED and never includes clipped ACK audio
in `tmp/input.wav`. A run that reaches the bounded suppression limit without
quiet cancels locally instead of recording residue. See `MANUAL_TESTING.md` for
the ACK-disabled, delayed-question, and immediate-question comparison cases.

`SILENCE_SECONDS` controls how much post-question quiet is required before the
question recording stops. `RECORDING_SILENCE_RMS`, default `750`, is the RMS
threshold used for question-recording end-of-speech detection. The recorder
uses a recent-window rule so steady background below that threshold and
occasional moderate noisy chunks do not force recording to wait for
`MAX_RECORD_SECONDS`, while speech-like chunks still extend the recording.

## Stable Knowledge Answers

Ordinary historical, linguistic, scientific, and other non-realtime questions
use the chat model's available knowledge. Hey Jarvis is instructed to give a
concise best-effort answer instead of claiming that internet access is required
merely because a question asks for a comparison, has a broad premise, involves
scholarly disagreement, or could benefit from verification. For example,
`中国古代人的语言交流跟现在中国哪个省份的方言类似？` should receive a
qualified answer that distinguishes historical periods and regions before
offering useful comparisons.

This path does not browse the web, retrieve citations, or prove that a model
answer is correct. It must not claim that sources or current facts were checked.
When knowledge is genuinely uncertain, the expected behavior is to state that
uncertainty briefly and still provide known context. Current or live questions
such as `今天有什么新闻` continue to require a configured structured provider
and are refused rather than answered from model memory. See `M047` in
`MANUAL_TESTING.md` for the optional live OpenAI behavior check.

### Response language and latency diagnostics

The current transcribed request controls the reply language independently of
earlier chat history. A request containing Chinese is answered in concise
Simplified Chinese. An explicit request for an English translation, term,
spelling, or pronunciation may include the requested English content, while
any surrounding explanation remains Chinese. English input continues to
receive an English response.

Successful pipeline loops emit `pipeline_timing` lines for transcription,
answer generation or local-tool routing, TTS, and playback. The final
`response_timing` line includes the recorded-audio duration, each stage,
`ready_to_play` (time after recording until synthesized audio is ready),
playback duration, `post_recording_total`, and route. For example:

```text
response_timing recording=5.840s transcription=0.800s answer=1.200s tts=0.900s ready_to_play=2.900s playback=4.100s post_recording_total=7.000s route=none
```

These are monotonic elapsed durations rather than wall-clock timestamps. They
help separate recording endpoint delay from OpenAI, local-tool, TTS, and
playback time. They do not log assistant answer text, raw audio, or credentials,
and they do not by themselves make the serial pipeline faster. See `M058` in
`MANUAL_TESTING.md` for the real voice comparison.

## Structured Tool Routing

`ENABLE_TOOLS=1` enables a deterministic routing boundary after transcription
and before chat generation. `TOOL_ROUTER_DEBUG=1` logs the selected route, tool,
params, and rule reason during the voice loop. Local time requests and simple
arithmetic are answered without asking the chat model. Weather requests are
answered through Open-Meteo when `WEATHER_PROVIDER=open-meteo`. FX requests are
answered through Frankfurter when `FX_PROVIDER=frankfurter`. Stock requests are
answered through Finnhub when `STOCK_PROVIDER=finnhub` and `FINNHUB_API_KEY` is
configured. Unsupported realtime-sensitive requests such as
`今天有什么新闻` are refused instead of falling back to chat memory or model
guessing.

`TOOL_ANSWER_NATURALIZATION=1` enables a separate OpenAI pass only for
successful Open-Meteo weather, Frankfurter FX, and Finnhub stock `ToolResult`
answers. The raw structured result remains authoritative and inspectable; the
naturalization prompt is allowed to rewrite the wording for speech but must
preserve numbers, units, currencies, timestamps, sources, caveats, and advice
disclaimers. Provider failures, missing credentials, realtime refusals,
calculator answers, local time answers, empty naturalization output, and
recoverable OpenAI naturalization errors use the deterministic raw answer
instead of falling back to chat speculation.

`WEATHER_PROVIDER=open-meteo` resolves city names through Open-Meteo geocoding
and fetches current, today, or tomorrow weather from Open-Meteo forecast data.
`DEFAULT_LOCATION=Singapore` is used when the user asks a weather question
without naming a place. Weather answers include source, location, observation or
forecast time, temperature, feels-like or weather-code context, and rain or
precipitation probability where Open-Meteo provides it.

`FX_PROVIDER=frankfurter` calls Frankfurter's single-pair rate endpoint and
calculates conversions locally. FX routing recognizes USD, SGD, CNY, EUR, JPY,
HKD, GBP, and AUD aliases in English and Chinese, including examples like
`100 USD to SGD`, `100 SGD exchange rate`, and `100美元兑人民币汇率是多少`.
When the base currency is omitted, `DEFAULT_BASE_CURRENCY=USD` is used. When
the quote currency is omitted, the configured default base is used as the quote
unless that would match the base, in which case SGD is used. FX answers include
the Frankfurter rate date and state that the result is a reference rate, not a
bank cash rate or executable trade quote. Unsupported currencies and malformed
provider data return structured tool errors without chat speculation.

`STOCK_PROVIDER=finnhub` enables Finnhub-backed stock quote requests.
`TOOL_HTTP_TIMEOUT_SECONDS=5` is the shared JSON request timeout.
`FINNHUB_API_KEY` is required for stock quotes; diagnostics and text debug report
it as configured or missing without printing the secret value.
Stock quote answers include current price, change, percent change, day high and
low, open, previous close, the Finnhub quote timestamp, plus caveats that market data may be delayed and the result is not trading advice. Unknown symbols, zero
current prices, provider failures, and malformed Finnhub responses return
structured tool errors without chat speculation.

Use the text debug path to inspect the route, params, tool result summary,
`raw_answer`, `naturalization_status`, and final answer plus provider
configuration. Text debug never calls OpenAI for naturalization and does not
require `OPENAI_API_KEY`:

```bash
python -m src.main --text "2 + 2"
python -m src.main --text "明天天气怎么样"
python -m src.main --text "weather in Tokyo today"
python -m src.main --text "100 USD to SGD"
python -m src.main --text "100美元兑人民币汇率是多少"
python -m src.main --text "AAPL stock price"
python -m src.main --text "苹果股价多少"
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
weather. F025 enables Frankfurter FX reference-rate conversion. F026 enables
Finnhub stock quotes for uppercase ticker symbols and a small conservative
company-name alias map. The personal US watchlist additionally recognizes
names such as SpaceX/SPCX, Alibaba/BABA, Costco/COST, TSMC/TSM, and
Netflix/NFLX. `Google`, `Alphabet`, and `谷歌` map to `GOOGL`; explicit `GOOG`
remains `GOOG`. Name-based requests still require a stock marker such as
`stock`, `股票`, or `股价`, so `苹果怎么样` does not trigger a quote.
Non-Finnhub stock providers still return
provider-not-configured answers.

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
- The assistant plays acknowledgement again immediately after `算了算了`,
  `没事`, or an ARMED no-speech timeout: keep the same post-playback suppression
  settings enabled. Local cancellation should log post-cancellation wake
  suppression, consume residual wake-positive chunks, wait for quiet audio, and
  only then report `ready for the next wake word`.

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
- `dependency:webrtcvad` reports an error: only when using
  `VAD_BACKEND=webrtc`, run `python -m pip install -r requirements-vad.txt`
  and repeat `python -m src.main --diagnose`.
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
- `FINNHUB_API_KEY` is reported as missing: set a real Finnhub key in `.env`
  before asking stock quote questions. The key is used only as the Finnhub
  `token` query parameter and is not printed in diagnostics or text debug.
- Stock quote errors such as unknown symbols or missing current prices return a
  structured tool error and do not fall back to chat speculation.
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

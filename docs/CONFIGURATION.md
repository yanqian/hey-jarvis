# Configuration reference

Copy `.env.example` to `.env`; never commit the resulting file. This document
owns the complete configuration inventory. Checked-in defaults remain
authoritative in `.env.example`, and invalid typed values fail with actionable
diagnostics.

## Backend and Realtime

| Setting | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | placeholder | OpenAI credential for real transcription, chat, TTS, and Realtime. |
| `BACKEND` | `pipeline` | `pipeline` or opt-in `realtime`. |
| `REALTIME_MODEL` | `gpt-realtime-2.1` | Realtime model. |
| `REALTIME_VOICE` | `alloy` | Realtime output voice, aligned with the local acknowledgement profile. |
| `REALTIME_OUTPUT_VOLUME` | `0.5` | Browser playback gain from `0.1` to `1.0`; target-Mac profile, not a universal loudness guarantee. |
| `REALTIME_IDLE_TIMEOUT_SECONDS` | `60` | Close an inactive session after playback finishes; active assistant playback is protected. |
| `REALTIME_MAX_DURATION_SECONDS` | `600` | Hard session-duration bound. |
| `REALTIME_SERVER_VAD_ENABLED` | `1` | Enable server turn detection. |
| `REALTIME_SERVER_VAD_THRESHOLD` | `0.8` | Server speech activation threshold. |
| `REALTIME_INPUT_NOISE_REDUCTION` | `far_field` | Input preprocessing: `far_field` for built-in speaker/mic, `near_field` for a headset, or `none`. |
| `REALTIME_INPUT_TRANSCRIPTION_ENABLED` | `1` | Enable rough-guide asynchronous input transcription. |
| `REALTIME_ACKNOWLEDGEMENT_MODE` | `cached` | Play the selected Realtime-quality WAV while connecting; use `realtime` for the paid same-session ACK or `local` for the prior `afplay` rollback. |
| `REALTIME_FAREWELL_MODE` | `cached` | Play the selected 580 ms local Mandarin `再见`; use `realtime` to restore same-session generated farewells. |
| `REALTIME_DEBUG` | `0` | Add bounded local lifecycle diagnostics. |
| `REALTIME_END_PHRASES` | bilingual list | Exact conservative transcription fallback phrases. |
| `REALTIME_BRIDGE_HOST` | `127.0.0.1` | Loopback host; keep local. |
| `REALTIME_BRIDGE_PORT` | `8770` | Loopback host port. |

The default Realtime path preloads the owner-selected `alloy` WAV locally and
starts it through the browser output element as soon as wake ownership is
released. WebRTC negotiation proceeds at the same time, and input stays muted
until both playback and configured-session readiness complete. Later answers
use the same browser element and configured gain. `realtime` retains the paid
same-session generated ACK for comparison; `local` retains the prior prepared
asset and separate `afplay` path as a rollback.
The built-in Mac profile uses
`REALTIME_INPUT_NOISE_REDUCTION=far_field`; a close headset microphone should
use `near_field`. The browser prefers standardized all-system-audio echo
cancellation when advertised and otherwise requires ordinary echo
cancellation. Re-run manual acceptance if room, device, or volume changes.

## Wake and acknowledgement

| Setting | Default | Purpose |
| --- | --- | --- |
| `WAKE_BACKEND` | `openwakeword` | Wake engine. |
| `WAKE_MODEL` | `hey_jarvis` | Built-in model name. |
| `WAKE_INFERENCE_FRAMEWORK` | `tflite` | Inference runtime; preferred on macOS ARM64. |
| `WAKE_PHRASE` | `hey jarvis` | Displayed accepted phrase. |
| `WAKE_THRESHOLD` | `0.5` | Wake detection score threshold; Realtime accepts the bounded `0.50` or `0.60` experiment choices. |
| `WAKE_VAD_THRESHOLD` | empty | Optional openWakeWord VAD threshold. |
| `VAD_BACKEND` | `disabled` | Optional local VAD; `webrtc` when installed. |
| `VAD_MODE` | `2` | WebRTC VAD aggressiveness, `0` through `3`. |
| `WAKE_DEBUG` | `0` | Log wake score fields during normal listening. |
| `WAKE_ACKNOWLEDGEMENT_ENABLED` | `1` | Play the prepared acknowledgement after wake. |
| `WAKE_ACKNOWLEDGEMENT_TEXT` | `嗯` | Display and cancellation-cleanup identity for the accepted ready cue. |
| `WAKE_ACKNOWLEDGEMENT_AUDIO_PATH` | `var/ack.mp3` | Prepared local file. |
| `WAKE_ACKNOWLEDGEMENT_MAX_DURATION_SECONDS` | `0.8` | Maximum accepted prepared cue duration. |
| `WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS` | `0.35` | Legacy fixed drain when guarding is disabled. |
| `WAKE_CONFIRMATION_FRAMES` | `2` | Consecutive positive wake frames required; Realtime accepts `2` or `3`. |
| `WAKE_DIAGNOSTICS_ENABLED` | `0` | CLI Realtime-only explicit opt-in for bounded, content-free wake evidence. |
| `WAKE_DIAGNOSTICS_DIR` | empty | Required local output directory when CLI wake diagnostics are enabled; contains `wake.jsonl` and rotations. |

The packaged Mac App has a separate persisted **Save wake-word tuning
diagnostics** switch under Privacy & Diagnostics. The same card persists the
Mac app's bounded wake experiment (`0.50` or `0.60`; `2` or `3` consecutive
frames) and displays the effective pair. It defaults off and does not
use an environment variable. The top-right control is always **Apply & Done**:
runtime-neutral changes close directly, while a change that stopped an active
or ready sidecar restores its prior safe state before closing Settings. See
`docs/MAC_APP_DIAGNOSTICS.md`
for the bounded JSONL schema, retention, export, clear, and calibration flow.

CLI Realtime reads its tuning from the persistent `.env` file and reports the
effective threshold/frame pair at startup. To collect the same numeric evidence
outside the Mac app, set `WAKE_DIAGNOSTICS_ENABLED=1` and provide an explicit
local `WAKE_DIAGNOSTICS_DIR`. No file or directory is created while the switch
is off. Invalid Realtime tuning, enablement, or destination values fail before
microphone capture starts. The CLI writer uses the same schema, event allowlist,
near-threshold policy, 512 KiB limit, and three rotated generations as the app;
it never stores audio, transcripts, answers, credentials, or provider content.

Acknowledgement guarding and post-playback suppression:

| Setting | Default |
| --- | --- |
| `ACK_GUARD_ENABLED` | `1` |
| `ACK_GUARD_MIN_QUIET_SECONDS` | `0.16` |
| `ACK_GUARD_QUIET_RMS` | `900` |
| `ACK_GUARD_MAX_BUFFER_SECONDS` | `1.50` |
| `POST_PLAYBACK_WAKE_COOLDOWN_SECONDS` | `1.0` |
| `POST_PLAYBACK_QUIET_SECONDS` | `0.5` |
| `POST_PLAYBACK_QUIET_RMS` | `500` |
| `POST_PLAYBACK_MAX_SUPPRESSION_SECONDS` | `6.0` |

The acknowledgement-only asynchronous `afplay` path uses the exact positive
`afinfo` metadata duration as its `-t` limit; normal answer playback remains
unbounded and unchanged. Microphone input is drained while acknowledgement
audio plays. A zero-overflow drain can preserve a bounded tail for ARMED
pre-roll; playback-only audio cannot trigger recording. Unsafe handoffs use the
quiet boundary. A question must continue after acknowledgement playback when
the hardware path has no acoustic echo cancellation.

`--prepare-acknowledgement` requires no OpenAI key or network call. It copies
the user-accepted canonical asset from
`assets/wake_acknowledgement_alloy.mp3` into a same-directory temporary file,
checks positive bounded duration with `afinfo`, requires the exact SHA-256 of
the accepted clear audible cue, and atomically replaces the configured runtime
asset only after validation. Missing-source, hash, duration, copy, or install
failure preserves the prior asset.

## ARMED and recording

| Setting | Default |
| --- | --- |
| `ARMED_NO_SPEECH_TIMEOUT_SECONDS` | `2.0` |
| `ARMED_VOICE_RMS` | `750` |
| `ARMED_MIN_RMS` | `750` |
| `ARMED_SNR_MULTIPLIER` | `2.5` |
| `ARMED_VOICE_WINDOW_SECONDS` | `0.30` |
| `ARMED_VOICE_REQUIRED_RATIO` | `0.75` |
| `ARMED_CLIP_REJECT_PEAK` | `32000` |
| `ARMED_PRE_ROLL_SECONDS` | `0.50` |
| `ARMED_BASELINE_SECONDS` | `0.30` |
| `ARMED_BASELINE_MIN_CHUNKS` | `3` |
| `ARMED_REQUIRE_BASELINE` | `1` |
| `ARMED_LAST_CHUNK_MUST_BE_VOICED` | `1` |
| `ARMED_VAD_REQUIRED_RATIO` | `0.50` |
| `ARMED_VAD_MIN_FRAMES` | `2` |
| `RECORDING_VAD_ENABLED` | `0` |
| `RECORDING_VAD_END_RATIO` | `0.25` |
| `RECORDING_VAD_SPEECH_RATIO` | `0.50` |
| `RECORDING_HANGOVER_SECONDS` | `0.30` |
| `RECORDING_END_SILENCE_SECONDS` | `1.5` |
| `MIN_VALID_SPEECH_SECONDS` | `0.50` |
| `MIN_TRANSCRIPT_LENGTH` | `2` |
| `CANCEL_PHRASES` | `取消,没事,不用了,算了,stop,cancel,never mind` |
| `SILENCE_SECONDS` | `1.5` |
| `MAX_RECORD_SECONDS` | `20` |
| `RECORDING_SILENCE_RMS` | `750` |
| `SAMPLE_RATE` | `16000` |

ARMED uses the larger of `ARMED_MIN_RMS` and its adaptive noise-floor
threshold, sustained-window confirmation, current-chunk confirmation, optional
VAD, and pre-roll. Logs expose `armed_summary`, `armed_trigger`,
`baseline_ready`, noise-floor, RMS, peak, clipping, overflow, and window
context without storing raw audio.

Optional recording VAD remains disabled by default even though the tested
Python 3.12 environment passed normal endpoint acceptance. Fixed RMS/silence and
`MAX_RECORD_SECONDS` remain safety controls.

Short cancel phrases and conservative spoken/noisy variants cancel locally
before chat, tools, answer TTS, playback, or history mutation. Command-like
continuations such as `不用了帮我查天气`, `取消我明天的闹钟`, or
`cancel my alarm tomorrow` are not treated as local cancellation.

## OpenAI pipeline models

| Setting | Default |
| --- | --- |
| `TRANSCRIBE_MODEL` | `gpt-4o-mini-transcribe` |
| `CHAT_MODEL` | `gpt-4o-mini` |
| `TTS_MODEL` | `gpt-4o-mini-tts` |
| `TTS_VOICE` | `alloy` |
| `TTS_INSTRUCTIONS` | Chinese presenter instruction |
| `TTS_SPEED` | `1.0` |

`TTS_INSTRUCTIONS` is sent as speech API instruction text.
`TTS_SPEED` must be between `0.25` and `4.0`.

## Structured tools

| Setting | Default | Purpose |
| --- | --- | --- |
| `ENABLE_TOOLS` | `1` | Route supported tools before general chat. |
| `TOOL_ROUTER_DEBUG` | `0` | Log route, tool, safe params, and rule reason. |
| `TOOL_ANSWER_NATURALIZATION` | `1` | Let OpenAI word successful remote tool results for speech. |
| `WEATHER_PROVIDER` | `open-meteo` | Weather provider. |
| `FX_PROVIDER` | `frankfurter` | Reference-rate provider. |
| `STOCK_PROVIDER` | `finnhub` | Stock quote provider. |
| `TOOL_HTTP_TIMEOUT_SECONDS` | `5` | Shared provider timeout. |
| `DEFAULT_LOCATION` | `Singapore` | Weather fallback. |
| `DEFAULT_BASE_CURRENCY` | `USD` | FX default. |
| `FINNHUB_API_KEY` | empty | Required only for Finnhub quotes. |

Naturalization may reword successful structured results but must preserve
numbers, units, currencies, timestamps, sources, and caveats. Provider failures
and missing credentials never fall back to speculative chat.

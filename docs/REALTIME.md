# Realtime guide

Realtime is the opt-in continuous WebRTC backend:

```bash
python -m src.main --backend realtime
```

Click **Arm hands-free audio** once per Chrome host launch. Say the configured
wake phrase; Python closes its wake microphone before Chrome obtains WebRTC
media. Follow-up turns and barge-in then remain inside one session without
another wake.

The first-turn ready contract is audible: wait until the local “在呢”
acknowledgement finishes, then speak. After wake, Python queues the Realtime
handoff immediately. Chrome acquires its audio track disabled, negotiates, and
posts its SDP to the loopback host. The host creates one already-configured
Realtime call; `session.created` is therefore the configuration barrier. The
browser separately records SDP-answer-to-data-channel-open and
data-channel-open-to-`session.created`; those two bounded phases reconcile to
the existing session-configuration total. RT001 also records the prepared
acknowledgement asset duration separately from wall-clock playback so player
and device overhead are not mistaken for spoken audio. Only
then does Python play “在呢”; after playback it sends one session-scoped
input-enable command. `host_connected` therefore means `input_ready`, not
merely that a transport exists. Speech before “在呢” is intentionally not
buffered by this version.

## Lifecycle and ownership

The pipeline remains the default. A Realtime session can close through a
semantic `end_conversation` tool call, an exact configured transcription
fallback phrase, idle or maximum duration, explicit stop, transport error, or
Ctrl+C. Browser media is closed before Python restores wake ownership.

Realtime advertises exactly two local functions:

- `calculator`, backed by the same safe bounded parser as the pipeline;
- `end_conversation`, a constrained no-argument semantic close control.

Valid calculator calls return one correlated `function_call_output` and request
spoken continuation in the same conversation. Weather, FX, stocks, shell
access, arbitrary routing, and pipeline history mutation are excluded. These
capabilities are outside the Realtime tool boundary.

## Language

The user’s current audio turn controls response language. Mandarin Chinese
receives concise Simplified Chinese and English receives English, even when the
languages alternate in one session. Mixed-language input follows the main
request. Translation, spelling, pronunciation, language-practice, and explicit
whole-response language requests may use their requested target language.

This policy uses the Realtime model’s current audio understanding rather than
the separate optional rough-guide input transcription.

## Privacy, credentials, and cost

Pre-wake audio is processed locally by Python, which uploads no pre-wake PCM,
transcript, or wake clip. After handoff, WebRTC sends session audio directly to
OpenAI and plays returned audio in Chrome.

The standard API key stays in Python. The browser sends its SDP only to the
loopback host; Python combines it with the validated session configuration and
uses OpenAI's unified WebRTC call interface. The browser receives only the SDP
answer, never an API credential. Realtime audio and optional input
transcription are billable.

Default reports retain bounded sanitized lifecycle/timing metadata. They
exclude keys, raw/base64 audio, audio deltas, transcripts, answers, tool
arguments/results, call IDs, SDP, and provider bodies. `REALTIME_DEBUG=1` adds
bounded local troubleshooting events, not production telemetry.

## Output and turn detection

The accepted built-in speaker/microphone profile uses:

```text
REALTIME_OUTPUT_VOLUME=0.1
REALTIME_SERVER_VAD_THRESHOLD=0.8
REALTIME_INPUT_NOISE_REDUCTION=far_field
```

Output volume is direct browser playback gain. Server VAD threshold controls
speech activation. `far_field` filters the laptop microphone input before VAD
and the Realtime model; use `near_field` for a close headset microphone or
`none` only for diagnosis. Chrome requests mandatory echo cancellation and
prefers the standardized `all` mode when the active track advertises it.
Sanitized host evidence records the requested mode, actual browser setting,
and remote playback-buffer start/stop separately from response generation.

The checked-in 0.1 gain remains conservative until the F073 built-in-speaker
acceptance run establishes a louder baseline. For a local trial, increase
`REALTIME_OUTPUT_VOLUME` gradually and repeat both a normal answer and a
deliberate barge-in. Do not treat headphones alone as built-in-speaker proof.
Server-managed interruption remains enabled.

Normal sessions do not create the optional Web Audio input-level analyser.
That analyser is enabled for exactly the next wake-triggered session only by
the F060 diagnosis workflow.

## End controls

`end_conversation` handles clear semantic requests to finish. Mentions,
quotations, translations, or requests to say a farewell are not close commands.

`REALTIME_END_PHRASES` remains a conservative fallback over completed input
transcription. Matching is exact after case, outer-punctuation, and whitespace
normalization. The asynchronous transcript is a rough guide only and is not
used for conversation meaning.

## Fake verification

```bash
python -m src.realtime.fake_smoke
```

This verifies wake, exclusive handoff, connection, two turns, interruption,
calculator output, closing, and wake recovery without browser, audio, network,
OpenAI, or wall-clock sleep.

## Private fixtures

Record local Git-ignored fixtures once:

```bash
python -m src.realtime.fixtures record wake --seconds 4
python -m src.realtime.fixtures record turn-1 --seconds 4
python -m src.realtime.fixtures record turn-2 --seconds 4
python -m src.realtime.fixtures record barge-in --seconds 4
python -m src.realtime.fixtures list
```

Fixtures live under `tmp/realtime-fixtures/`. The manifest retains duration and
capture health, not transcript content.

## Evaluation commands

Live commands open real devices, connect to OpenAI, may incur cost, and require
explicit authorization for every run. Offline commands evaluate an existing
sanitized observation.

RT001 verifies saved-wake handoff, exclusive microphone ordering, connection,
configured-session readiness, acknowledgement-gated input, cleanup, timing
attribution, and wake recovery. It needs no fresh human speech:

```bash
python -m src.evals.realtime_handoff live
python -m src.evals.realtime_handoff offline path/to/observation.json
```

RT002 replays two saved turns after browser echo cancellation and verifies one
continuous session. Routine runs require no fresh speech and evaluate lifecycle
continuity, not transcript or answer semantics:

```bash
python -m src.evals.realtime_two_turn live
python -m src.evals.realtime_two_turn offline path/to/observation.json
```

RT004 connects session A, closes and restores wake ownership, then connects a
distinct session B without another Arm action:

```bash
python -m src.evals.realtime_close_recovery live
python -m src.evals.realtime_close_recovery offline path/to/observation.json
```

Its versioned timing report includes the first-minus-second Web Audio
comparison. Normal sessions report zero for the disabled audio-analysis
aggregate and all six nested fields. Nested timing values reconcile to their
aggregate without being counted twice.

RT003 is the assisted no-headphones barge-in check:

```bash
python -m src.evals.realtime_barge_in live
python -m src.evals.realtime_barge_in offline path/to/observation.json
```

It has one fail-closed pre-session readiness gate. The one natural interruption
utterance is also audible-answer confirmation, so there is no second
terminal/chat round trip that can let the active answer expire.

If RT003 does not observe `host_speech_started`, run diagnosis before tuning:

```bash
python -m src.evals.realtime_input_diagnosis live
python -m src.evals.realtime_input_diagnosis offline path/to/observation.json
```

F060 compares bounded normalized input levels for `no_remote_playback` and
`remote_playback`, then classifies `capture_path`,
`server_vad_sensitivity`, `full_duplex_attenuation`, `event_orchestration`, or
`inconclusive`. It is not automatic tuning and not an RT003 pass, and it does
not change `REALTIME_SERVER_VAD_THRESHOLD`.

Negotiation failures retain only a strict diagnostic allowlist such as HTTP
status, OpenAI `error.type` and `error.code`, request ID, retry-after, and safe
rate-limit fields. The evaluator never retains the full provider response body.

See [Manual testing](../MANUAL_TESTING.md) for the M057–M066 device procedures
and [Troubleshooting](TROUBLESHOOTING.md) for host failures.

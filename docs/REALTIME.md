# Realtime guide

Realtime is the opt-in continuous WebRTC backend:

```bash
python -m src.main --backend realtime
```

Click **Arm hands-free audio** once per Chrome host launch. Say the configured
wake phrase; Python closes its wake microphone before Chrome obtains WebRTC
media. Follow-up turns and barge-in then remain inside one session without
another wake.

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

The standard API key stays in Python. The browser receives a server-minted
ephemeral client secret, not the standard key. Realtime audio and optional
input transcription are billable.

Default reports retain bounded sanitized lifecycle/timing metadata. They
exclude keys, ephemeral credentials, raw/base64 audio, audio deltas,
transcripts, answers, tool arguments/results, call IDs, SDP, and provider
bodies. `REALTIME_DEBUG=1` adds bounded local troubleshooting events, not
production telemetry.

## Output and turn detection

The accepted built-in speaker/microphone profile uses:

```text
REALTIME_OUTPUT_VOLUME=0.1
REALTIME_SERVER_VAD_THRESHOLD=0.8
```

Output volume is direct browser playback gain. Server VAD threshold controls
speech activation. These values passed the accepted device trials but are not
universal; changing room, speaker, or microphone conditions requires renewed
manual acceptance.

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
cleanup, timing attribution, and wake recovery. It needs no fresh human speech:

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

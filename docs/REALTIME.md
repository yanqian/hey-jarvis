# Realtime guide

Realtime is the opt-in continuous WebRTC backend:

```bash
python -m src.main --backend realtime
```

Click **Enable voice assistant** once per Chrome host launch. Say the configured
wake phrase; Python closes its wake microphone before Chrome obtains WebRTC
media. Follow-up turns and barge-in then remain inside one session without
another wake.

The first-turn ready contract is audible: wait until the Mandarin
“嗯，我在，请说。” acknowledgement finishes, then speak. After wake, Python
releases its microphone and queues the Realtime handoff immediately. The
default `cached` mode starts the validated Realtime-derived WAV in the browser
while Chrome concurrently acquires a disabled audio track and negotiates the
single configured Realtime call. `session.created` is the configuration
barrier. Input opens only after both that barrier and cached playback
completion, regardless of which finishes first. The cached cue and subsequent
Realtime answers use the same browser audio element and configured gain;
switching from the cue to the remote stream does not create a second output
path. `host_connected` therefore means `input_ready`, not merely that a
transport exists. Speech before the cue completes is intentionally not
buffered by this version. Explicit `realtime` and `local` acknowledgement modes
remain available for comparison and rollback.

## Lifecycle and ownership

The pipeline remains the default. A Realtime session can close through a
semantic `end_conversation` tool call, an exact configured transcription
fallback phrase, idle or maximum duration, explicit stop, transport error, or
Ctrl+C. Browser media is closed before Python restores wake ownership.
The idle window defaults to 60 seconds and restarts after confirmed assistant
playback stops. Idle closure is suppressed while assistant playback is active;
the maximum session duration remains authoritative if a playback-stop event is
missing.

Realtime advertises exactly six allowlisted local functions:

- `calculator`, backed by the same safe bounded parser as the pipeline;
- `weather`, backed by the existing Open-Meteo provider, with
  `DEFAULT_LOCATION=Singapore` when the user does not name a location;
- `local_time`, backed by the host's local clock and timezone with no
  model-controlled arguments or network access;
- `fx`, backed by the existing Frankfurter provider and configured currency
  defaults, with bounded amounts, supported currency codes, reference-rate
  date, rounding, and the existing non-trade-quote caveat;
- `stock`, backed by the existing credentialed Finnhub provider for one
  conservative ticker, with quote timestamp, delayed-data warning, and
  non-trading-advice caveat;
- `end_conversation`, a constrained no-argument semantic close control.

Valid calculator, weather, local-time, FX, and stock calls return one correlated
`function_call_output` and request spoken continuation in the same
conversation. Weather accepts current, today, and tomorrow intent plus an
optional explicit place. FX accepts an optional positive amount and optional
supported base/quote codes; omitted fields retain the existing provider
defaults. Python owns each fixed-provider request, timeout, and structured
failure boundary; the browser remains a content-blind loopback relay. Provider
work does not hold the lifecycle lock, and a late result cannot cross into a
stopped or replacement session. Stock requires `FINNHUB_API_KEY`; a missing key
or unknown ticker remains a bounded provider error and never becomes invented
market data. Trading actions, shell access, and arbitrary routing remain
outside the Realtime tool boundary. Pipeline history mutation also remains
excluded.

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
REALTIME_VOICE=alloy
REALTIME_OUTPUT_VOLUME=0.5
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

The default cached acknowledgement and later answer use the same browser audio
element, `alloy` voice profile, and checked-in `0.5` gain. That gain is the
target-Mac profile, not a universal device-loudness guarantee. If local hardware
requires another gain, repeat both a normal answer and a deliberate barge-in.
Do not treat headphones alone as built-in-speaker proof. Server-managed
interruption remains enabled.

### A/B acknowledgement experiment

The completed selection retained a natural Mandarin bridge,
`嗯，我在，请说。`, as a validated 2,429 ms local WAV. The default `cached`
mode starts that asset immediately after wake while negotiation runs in
parallel; input opens only after both playback and configured-session readiness.
Set `REALTIME_ACKNOWLEDGEMENT_MODE=realtime` to restore the paid same-session
generated ACK, or `local` to roll back to the prior 480 ms `afplay` asset without
changing the classic pipeline.

The acknowledgement response is audio-only, disables tools, and uses an explicit
Mandarin instruction because no user audio exists yet from which to infer a
language. It intentionally uses the Realtime API's default output-token limit:
low numeric caps can truncate even a very short audio response before its
completion event. The same rule applies to the native farewell; its exact-word
instruction and existing bounded shutdown timeout remain the length and safety
guards.

After explicit microphone, speaker, network, and paid-API authorization, start
and arm the ordinary Realtime host, ensure the private wake fixture exists, and
run:

```bash
python -m src.evals.realtime_acknowledgement live
```

If same-Mac fixture playback does not trigger the current wake detector, use
`live --manual-wake`; the runner pauses before each trial so the owner can say
the wake phrase naturally. If the local trial completed but the Realtime trial
failed, `--reuse-latest-local` validates and reuses only the latest sanitized
complete local lifecycle so a retry does not create another paid local trial.

The runner plays the local trial first and the Realtime trial second, restores
wake ownership after each, then asks for the listener's perceptual verdict. Its
untracked JSON evidence separates configured-session readiness, response
creation, browser-observable playback start, playback completion, input ready,
local asset duration, and cleanup. Browser playback start is not physical
acoustic onset. Evidence retains only model/voice/volume identifiers, bounded
lifecycle timing, outcomes, and the verdict—never audio, transcripts, response
text, credentials, SDP/ICE, provider payloads, or tool data.

Normal sessions do not create the optional Web Audio input-level analyser.
That analyser is enabled for exactly the next wake-triggered session only by
the F060 diagnosis workflow.

## End controls

`end_conversation` handles clear semantic requests to finish. Mentions,
quotations, translations, or requests to say a farewell are not close commands.
After a matched semantic or exact-phrase ending, browser input is muted and the
default `cached` mode plays the owner-selected 580 ms Mandarin `再见` WAV through
the ordinary browser audio element and configured volume without creating a
farewell model response. Media teardown and wake recovery wait for local
playback completion; a bounded timeout or playback failure falls back to
immediate safe cleanup. `REALTIME_FAREWELL_MODE=realtime` restores the former
same-session generated farewell and waits for both response and output-buffer
completion. English and automatic language selection are intentionally
deferred.

`REALTIME_END_PHRASES` remains a conservative fallback over completed input
transcription. Matching is exact after case, outer-punctuation, and whitespace
normalization. The asynchronous transcript is a rough guide only and is not
used for conversation meaning.

## Fake verification

```bash
python -m src.realtime.fake_smoke
```

This verifies wake, exclusive handoff, connection, two turns, interruption,
calculator output, mocked default-Singapore weather, FX, and stock outputs,
injected local-time output, closing, and wake recovery without browser, audio,
network, OpenAI, or wall-clock sleep.

## Private fixtures

Record local Git-ignored fixtures once:

```bash
python -m src.realtime.fixtures record wake --seconds 4
python -m src.realtime.fixtures record turn-1 --seconds 4
python -m src.realtime.fixtures record turn-2 --seconds 4
python -m src.realtime.fixtures record barge-in --seconds 4
python -m src.realtime.fixtures list
```

Fixtures live under `artifacts/audio/fixtures/`. Each scenario has one
canonical replay WAV; the manifest retains duration, format, and capture
health, not transcript content. Original recordings used to create a replay
are private local source material and are not required for evaluation.

To create a canonical replay from a private source directory:

```bash
python -m src.realtime.fixtures trim turn-1 \
  --start 0.3 --end 2.8 \
  --source-root /path/to/private-realtime-recordings
```

## Evaluation commands

Live commands open real devices, connect to OpenAI, may incur cost, and require
explicit authorization for every run. Offline commands evaluate an existing
sanitized observation.

### Curated Realtime acknowledgement capture

The candidate workflow is deliberately separate from normal conversations. It
must be explicitly armed for one wake, digitally records only the remote
WebRTC stream correlated to `purpose=acknowledgement`, validates the fixed
Mandarin phrase, and writes a bounded WAV plus manifest under the Git-ignored
`artifacts/audio/candidates/mandarin-ack/` directory. It never records the microphone or
automatically retains answers and farewells.

After starting and arming the ordinary Realtime host, one explicitly authorized
paid capture is:

```bash
python -m src.evals.realtime_ack_capture capture candidate-01
```

Audition candidates locally. Promote only the exact candidate the owner selects:

```bash
python -m src.evals.realtime_ack_capture promote \
  artifacts/audio/candidates/mandarin-ack/candidate-01.wav \
  --owner-confirmed
python -m src.evals.realtime_ack_capture prepare
```

Promotion creates the canonical WAV and privacy-safe manifest under `assets/`;
preparation verifies the digest and installs `var/realtime-ack.wav` without a
network request. The candidate directory may contain deliberately retained
audio and must not be attached to support bundles or committed.

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

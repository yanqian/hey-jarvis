# F061 RT003 Live Attempts

## Attempt 1: Operator Gate Exposed Session Idle Timeout

- Date: 2026-07-23
- Authorization: the user explicitly authorized this F061/RT003 run to use the
  microphone, send one test utterance plus optional transcription to OpenAI,
  and incur the associated API cost.
- Result: FAIL at `long_answer` before the authorized utterance was spoken.

The first version-2 attempt connected successfully and stopped at the first
operator gate. While the operator coordinated through Codex, the already-active
Realtime session reached its existing idle timeout. The subsequent local
`/api/long-answer` request therefore returned an HTTP error because no active
host remained. Cleanup restored `wake_owned` with the wake microphone open.
Saved evidence contained only allowlisted lifecycle metadata; no test
utterance, transcript, audio, credential, or tool content was retained.

### Coding Retry

The first gate now precedes wake-fixture playback and session establishment.
Once the operator advances it, the runner wakes, connects, and promptly sends
the long-answer request without charging human coordination time against the
active session's idle timeout. The second gate remains after the exact active
`host_response_created` marker and before the one real speech action.

Focused RT003 and documentation tests pass with 22 tests. A deterministic
regression proves that neither wake playback nor the long-answer request can
occur before the first gate.

### Failure Analysis

- Failure domain: implementation_gap
- Failure summary: the operator readiness gate was inside the active session
  and could outlive its idle timeout.
- Harness improvement: live eval protocols with human coordination should place
  readiness gates before acquiring timeout-bound runtime resources.
- Follow-up: rerun the still-authorized RT003 attempt; the authorized utterance
  was not consumed by this pre-speech failure.

## Attempt 2: Audible Confirmation Outlived the Long Answer

- Date: 2026-07-23
- Result: FAIL before a valid active-session interruption utterance.

The pre-session gate correction worked: the runner connected, promptly created
the long counting response, and the operator heard it. However, relaying the
audible confirmation back through Codex and then into the runner outlived the
remaining response duration. When the second gate advanced, the long response
had already completed naturally, so the runner correctly rejected the attempt
instead of relabeling later speech as barge-in evidence. Cleanup again restored
fresh wake ownership.

### Coding Retry

The separate post-creation terminal gate is removed. After pre-session
readiness, the runner connects, creates the long response, and immediately
observes the one real near-end action. The prepared operator waits until
counting is audible and speaks the interruption directly; that utterance is
both in-band audible confirmation and barge-in evidence. A naturally completed
long response now fails immediately and precisely instead of waiting for a
continuation timeout. No prompt length, model, voice, VAD, output volume,
capture setting, product interruption logic, or RT003 oracle was changed.

### Failure Analysis

- Failure domain: implementation_gap
- Failure summary: a second out-of-band Codex/terminal round trip could exceed
  the remaining deterministic answer duration.
- Harness improvement: real-time human evals should use a single prepared
  in-band action when that action itself proves the perceptual precondition.
- Follow-up: run with the operator prepared before session start and instruct
  them to speak directly when counting becomes audible, without another chat
  confirmation.

## Attempt 3: PASS

- Date: 2026-07-23T08:49:23Z
- Scenario: RT003 version 2
- Evidence tier: `live_near_end`
- Hardware: built-in Mac microphone and speaker, without headphones
- Result: PASS

The operator confirmed readiness before session acquisition, then spoke one
natural near-end interruption directly after counting became audible. Sanitized
active-session lifecycle evidence shows:

```text
host_connected=true
long_response_created=true
host_speech_started=true
old_response_reason=cancelled
cancellation_latency_ms=69
continuation_reason=completed
host_stopped=true
final_state=wake_owned
wake_microphone_open=true
```

The 69 ms cancellation is within RT003's unchanged 1000 ms limit. The
continuation completed, bounded stop ran, and the Python wake microphone
reopened. The saved local evidence contains only allowlisted lifecycle metadata;
it contains no transcript text, utterance text, audio/base64 data, credential,
or tool content. No Realtime model, voice, VAD threshold, output volume,
capture/AEC setting, or product interruption behavior was changed.

# F060 Authorized Live Diagnostic Attempt

## Summary

- Date: 2026-07-23T07:29:43Z
- Feature: F060
- Result: blocked before speech collection by OpenAI WebRTC HTTP 429
- Authorization: the user explicitly authorized microphone use, sending the
  two F060 test utterances and optional transcription to OpenAI, and associated
  API charges.

## Attempts

Two initial real-device starts were made approximately two minutes apart. A
later user-requested retry produced the same result. All three attempts:

- used the Chrome app-mode host with the built-in microphone;
- acquired browser processing with echo cancellation, noise suppression,
  automatic gain control, 48 kHz mono capture, and output volume 0.1;
- produced bounded normalized input-level summaries from the WebRTC microphone
  stream;
- failed during WebRTC negotiation with HTTP 429 before `host_connected`;
- did not reach the silence/no-playback/remote-playback prompts, so neither
  authorized test utterance was sent;
- stopped the browser media path and restored `wake_owned` with the Python wake
  microphone open.

The second attempt saved bounded sanitized failure evidence to
`tmp/realtime-evals/F060-diagnosis.json`. The local file contains only
allowlisted lifecycle metadata and normalized RMS/peak summaries; it contains
no audio, transcript, utterance text, credential, provider response body, or
tool payload.

## Coding Retry From Live Evidence

The first attempt exposed that the guided runner waited for its full startup
timeout after a browser `host_error`. The runner now:

- fails immediately when a new startup `host_error` appears;
- requests the existing bounded cleanup path;
- saves the precise `session_start` failure stage;
- accepts bounded CLI controls for baseline and speech-window duration so the
  operator has enough time to follow both prompts.

Focused diagnosis, host, F059 regression, and documentation verification passes
41 tests. Final `./init.sh` passes harness verification, 291 project tests,
dry-run, fake-backend, and Realtime fake smoke. This is not the required
successful live diagnostic evidence and does not claim a root-cause category.

## Failure Analysis

- Failure domain: external_behavior_gap
- Failure summary: OpenAI rejected WebRTC SDP negotiation with HTTP 429 before
  an active Realtime session existed.
- Harness improvement: none; evaluator gating and sanitized failure persistence
  correctly keep F060 unfinished.
- Follow-up: retry the same authorized live command after the OpenAI Realtime
  rate/quota condition clears, then run a separate cold-start evaluator.

## Later Retry

The user explicitly requested another F060 retry after reviewing the meaning of
HTTP 429. Recovery verification again passed 291 project tests before launch.
The Chrome host was already armed, acquired the same processed 48 kHz mono
microphone path, and OpenAI again returned `WebRTC negotiation failed (429)`
before `host_connected`. The fail-fast runner saved sanitized `session_start`
failure evidence, restored `wake_owned`, and neither human utterance was sent.
The runtime and Chrome test window were then closed to release local resources.

## Safe Error-Diagnostic Retry

The user requested a bounded negotiation-error diagnostic within F060. After
the strict browser/coordinator/evidence allowlist was implemented and 292
project tests passed, an authorized real-device start produced:

```text
httpStatus=429
errorType=insufficient_quota
errorCode=insufficient_quota
failureStage=session_start
```

No allowlisted request ID, retry-after, or rate-limit remaining/reset header was
available to the browser response. The saved evidence contains no full provider
body, SDP, authorization header, ephemeral secret, API key, audio, transcript,
or utterance text. The failure happened before `host_connected`; neither human
utterance was sent, and cleanup restored `wake_owned` with the wake microphone
open.

## Connected Retry After Credit Restoration

After the user restored API credit, the same authorized F060 command connected
successfully. The first connected attempt used the original short operator
window and was discarded after the user confirmed they had not spoken during
the no-playback prompt. It is not treated as valid diagnostic evidence.

The valid retry extended both guided speech windows so the user could act after
each visible prompt. It produced these sanitized measurements:

```text
silence_max_rms=0.0128
no_remote_playback_max_rms=0.5671
no_remote_playback_speech_started=true
remote_playback_max_rms=0.1456
remote_playback_speech_started=true
cleanup_restored=true
```

During the remote-playback phase, `host_speech_started` was followed by the
counting response completing as `cancelled` about 74 ms later. A continuation
response was then created. The browser stopped its media path and the
coordinator restored `wake_owned` with `wake_microphone_open=true`.

The extended operator windows generated more level events than the bounded
saved-report allowance. This exposed a diagnosis-only defect where summary
calculation inherited the persistence cap and initially returned
`inconclusive`. The retry implementation now computes summaries from all
strictly validated in-memory level windows while continuing to persist only
the capped sanitized report. Reclassification of the same live run returns:

```text
category=event_orchestration
window_counts=[7,32,39]
```

The evidence remains diagnosis-only. It does not alter Realtime thresholds,
output volume, microphone constraints, or RT003's recorded F059 verdict.

FAST_CODING_EVIDENCE: F060

CODING_PASS: F060

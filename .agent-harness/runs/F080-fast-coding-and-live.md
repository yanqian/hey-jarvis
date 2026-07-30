# F080 Fast Coding and Live Acceptance

Feature: F080 - Align acknowledgement and Realtime voice profile

Date: 2026-07-28
Result: Coding and user-led target-Mac acceptance passed; separate evaluator pending

## Implementation

- Changed the checked-in Realtime voice default from `marin` to `alloy`.
- Changed the checked-in browser output-volume default from `0.1` to `0.5`.
- Removed the rejected acknowledgement preparation speed `3.0` from active
  defaults and restored the conservative independently validated speed `1.0`.
- Preserved the accepted 480 ms local alloy `嗯` asset, local playback,
  configured-session readiness before acknowledgement, input enablement only
  after acknowledgement completion, WebRTC media processing, interruption,
  timeout, privacy, and cleanup behavior.
- Updated configuration, Realtime guidance, manual acceptance, diagnostics,
  and focused default/request-shape regression contracts.

## Offline verification

- 106 focused config, Realtime server, OpenAI, acknowledgement preparation,
  diagnostics, documentation, and regression tests passed.
- `node --check src/realtime_host/static/app.js` passed.
- Realtime fake smoke passed with two turns, barge-in, all accepted tools,
  semantic ending, cleanup, and wake recovery.
- Final `./init.sh` passed with 371 project tests, pipeline fake smoke, and
  Realtime fake smoke.

## User-led target-Mac acceptance

The user explicitly authorized sending live Mac microphone audio to OpenAI
Realtime for this run. The active local configuration used Realtime voice
`alloy`, output volume `0.5`, far-field input reduction, and the accepted
480 ms local alloy `嗯` asset.

Two built-in-microphone/speaker sessions recorded:

- 48 kHz mono input with echo cancellation, noise suppression, and automatic
  gain control enabled;
- configured session readiness before `ack_started`, `ack_completed` before
  `enable_input` and `host_connected`, and no speech event before input ready;
- one ordinary audible answer;
- deliberate speech during a longer answer followed by
  `host_response_done reason=cancelled`, then a continuation;
- semantic `再见` closure through `host_end_conversation_tool`;
- browser stop before `wake_microphone_reopened`, ending in `wake_owned`; and
- one earlier idle-timeout cleanup that also restored wake ownership.

The user reported that the Realtime voice is closer to the acknowledgement
than before and that volume `0.5` is suitable. The user also reported an
important residual perceptual difference: the local `嗯` sounds male while
the Realtime conversation sounds female. This evidence therefore supports
perceptual improvement, not identical synthesis or voice identity.

No audio, transcript, answer, credential, SDP, ICE, tool content, or provider
payload is retained in this record.

FAST_CODING_EVIDENCE: F080
CODING_PASS: F080

# F063 Fast Coding Evidence

FAST_CODING_EVIDENCE: F063

## Implementation

- Added the versioned zero-human-action RT002 contract and generic schema entry.
- Added integrity-checked private wake/turn fixtures, an offline oracle, and a
  live runner that proves exactly one connection/session, two ordered atomic
  audio conversation items, two completed responses, bounded explicit stop,
  and restored wake ownership.
- Added a loopback-only, active-session-only fixture command. It carries
  bounded validated PCM in memory to the armed browser, submits it through the
  existing WebRTC data channel, and excludes audio and content from lifecycle
  reports and committed evidence.
- Resamples the private mono 16 kHz PCM16 fixture to one mono 24 kHz PCM16
  Realtime audio item without changing the real microphone processing profile.
- The runner rejects a cancelled or failed first response immediately and
  never advances to the second fixture on a non-completed response.
- Added deterministic pass/failure coverage, CLI, privacy assertions, browser
  script assertions, and operator documentation.

## Corrective Live Investigation

The first authorized attempt did not reach the host because the sandbox blocked
Python loopback access. The first real-host attempt then connected normally but
same-device acoustic `afplay` of `turn-1` was removed by active browser echo
cancellation, producing no speech event before idle timeout.

The first data-channel retry used streaming `input_audio_buffer.append`.
Natural pauses inside the saved fixture were segmented by server VAD into
multiple utterances; later segments cancelled an in-progress response. The
strict oracle correctly rejected three speech starts rather than two and did
not relabel the run as passing.

RT002 is a session-continuity scenario, while RT003 owns live VAD/barge-in
behavior. The corrected runner therefore uses the officially supported atomic
`conversation.item.create` `input_audio` form over the WebRTC data channel,
followed by one `response.create` per fixture. This produces one auditable
submission and requires one completed response before the second turn.

## Deterministic Verification

- Focused RT002/host/shared-runner/RT003/documentation tests: 65 passed.
- Full project discovery: 323 passed.
- Browser JavaScript syntax: passed.
- Python compilation: passed.
- Pipeline fake smoke: passed.
- Realtime fake smoke: passed.
- Final root `./init.sh`: passed.

## Authorized Fixture-Replay Verification

- Date: 2026-07-23T13:48:09Z
- Scenario: RT002 version 1
- Evidence tier: `fixture_replay`
- Authorization: the user explicitly authorized this F063/RT002 run to open
  the microphone, send two recorded test utterances plus optional
  transcription to OpenAI, and incur associated API charges.
- Human speech during the scenario: none required or requested.
- Browser capture profile: echo cancellation, noise suppression, and automatic
  gain control enabled; 48 kHz mono microphone.
- Result: PASS.

Observed sanitized lifecycle order:

```text
wake_microphone_closed
host_microphone_requested
host_microphone_acquired
host_connected
host_fixture_submitted
host_response_created
host_response_done(completed)
host_fixture_submitted
host_response_created
host_response_done(completed)
host_stopped
wake_microphone_reopened
```

All scoped events used one fresh session identity. The final report was
`wake_owned` with the wake microphone open. The local evidence under
`tmp/realtime-evals/` contains only allowlisted lifecycle metadata; it contains
no raw/base64 audio, transcript, answer, credential, ephemeral secret, SDP,
provider body, tool content, or private fixture bytes and remains untracked.

CODING_PASS: F063

# F062 Fast Coding Evidence

FAST_CODING_EVIDENCE: F062

## Implementation

- Added a backward-compatible generic Realtime scenario schema supporting
  `offline`, `fixture_replay`, `live_host`, and `live_near_end`.
- Added the versioned RT001 contract for saved wake, exclusive microphone
  handoff, connection, bounded explicit stop, and wake recovery without a user
  question or assistant response.
- Added shared injected request, clock, playback, polling, privacy
  sanitization, and bounded cleanup machinery.
- Added the automatic RT001 live runner and offline CLI using the same oracle.
- Added deterministic pass/failure coverage and documentation.

## Deterministic Verification

- Focused RT001, RT003 regression, and documentation tests: 35 passed.
- Full project discovery: 308 passed.
- Python compilation: passed.
- Realtime fake smoke: passed.
- Final root `./init.sh`: passed.

## Authorized Live-Host Verification

- Date: 2026-07-23T13:11:49Z
- Scenario: RT001 version 1
- Evidence tier: `live_host`
- Authorization: the user explicitly authorized this F062/RT001 run to open
  the microphone, send session environmental audio plus optional
  transcription to OpenAI, and incur associated API charges.
- Input: existing Git-ignored private `wake` replay fixture.
- Human speech during the scenario: none required or requested.
- Result: PASS.

Observed sanitized lifecycle order:

```text
wake_microphone_closed
host_microphone_requested
host_microphone_acquired
host_connected
host_stopped
wake_microphone_reopened
```

At `host_connected`, the report was `host_active` with the Python wake
microphone closed. After bounded explicit stop, the final report was
`wake_owned` with the wake microphone open. All session-scoped events used one
fresh session identity.

The local evidence file under `tmp/realtime-evals/` contains only allowlisted
lifecycle metadata. It contains no raw/base64 audio, transcript, credential,
ephemeral secret, SDP, provider body, tool content, or private fixture bytes,
and remains untracked.

CODING_PASS: F062

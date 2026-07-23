# F064 Fast Coding Evidence

FAST_CODING_EVIDENCE: F064

## Implementation

- Normalized RT004 before implementation because the selected feature did not
  yet have an authoritative SPEC section.
- Added the versioned RT004 offline/live-host contract with zero routine human
  actions and strict audio, transcript, credential, provider-body, and secret
  exclusions.
- Added a fail-closed oracle and automatic runner for two saved-wake cycles:
  connect session A, explicitly stop, prove browser media stop before Python
  wake microphone reopen, repeat the same private wake, connect a distinct
  session B, and repeat bounded cleanup.
- Added deterministic coverage for missing, duplicated, stale, and misordered
  lifecycle events; concurrent microphone ownership; reused session identity;
  failed next-wake connection; and either cleanup timeout.
- Added offline/live CLI and operator documentation. RT004 does not ask a
  question or judge transcript/answer semantics.

## Verification

- Focused RT001-RT004/shared-runner/documentation suite: 58 tests passed.
- Full project discovery: 332 tests passed.
- Final project recovery verification: `./init.sh` passed with 332 project
  tests, dry-run, pipeline fake-backend smoke, and Realtime fake smoke.

## Authorized live-host acceptance

- Scenario: RT004 version 1.
- Evidence tier: `live_host`.
- Authorization: the user explicitly authorized this F064/RT004 execution to
  open the microphone, send environment audio and optional transcription
  during two Realtime sessions to OpenAI, and incur the associated API cost.
- Device path: built-in microphone and speaker; Chrome reported echo
  cancellation, noise suppression, and automatic gain control enabled at
  48 kHz mono.
- Human action: one browser Arm click only. No fresh speech was requested or
  provided; the same existing private wake fixture was replayed twice.
- Result: PASS. Exactly two fresh connections used distinct session identities.
  For each cycle, browser ownership was exclusive while active, explicit stop
  preceded Python wake-microphone reopen, and recovery reached `wake_owned`.
  Final cleanup restored the wake microphone before the host and Chrome test
  window were closed.
- Content/privacy: the durable result contains only bounded lifecycle summaries.
  Raw/private audio, transcript text, credentials, provider payloads, and local
  `tmp/` evidence are not committed.

CODING_PASS: F064

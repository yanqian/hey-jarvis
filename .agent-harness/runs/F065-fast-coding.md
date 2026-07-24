# F065 Fast Coding Evidence

FAST_CODING_EVIDENCE: F065

## Root cause

- Two prior manual trials captured wake and completed transcription but did not
  emit `host_end_phrase_matched`; GPT handled the farewell as ordinary
  conversation and cleanup occurred only through `idle_timeout`.
- Deterministic tests already proved that an exact normalized `再见。` matches.
  The defect boundary was therefore reliance on a separate asynchronous
  rough-guide ASR transcript for semantic control, not microphone capture,
  Realtime understanding, or media teardown.

## Implementation

- Preserved exact completed-transcription matching as a conservative fallback.
- Added exactly one constrained `end_conversation` Realtime function alongside
  the existing calculator. Instructions require an unambiguous user intent to
  leave, forbid substantive spoken continuation, and exclude mentions,
  quotations, translations, and requests to say farewell.
- Validated active same-session empty-object calls with bounded arguments,
  de-duplicated calls, recorded only sanitized outcomes, and reused the
  existing single `end_phrase` stop/media-cleanup path without tool output or
  continuation response.
- Added browser handling for both the finalized function-arguments event and
  the completed response output item.
- Kept malformed, nonempty, oversized, duplicate, stale, unknown, and
  calculator paths fail-safe and bounded.
- Verified tool and event shapes against the current official OpenAI Realtime
  function-calling documentation.

## Verification

- Focused coordinator/fake-smoke/controller/documentation suite: 37 tests
  passed.
- Full project discovery: 334 tests passed.
- JavaScript syntax check passed.
- Final project recovery verification: `./init.sh` passed with 334 project
  tests, dry-run, pipeline fake-backend smoke, and Realtime fake smoke.

## Authorized live-human acceptance

- The user explicitly authorized F065 to open the built-in microphone, send
  session audio and optional transcription to OpenAI, and incur API cost.
- Two setup attempts honestly remained invalid: one farewell preceded browser
  capture and one coordination pause exceeded the configured idle window.
- The accepted continuous attempt connected, captured one human farewell, and
  emitted exactly one `host_end_conversation_tool`.
- The coordinator requested exactly one `end_phrase` stop at the same monotonic
  timestamp. Browser media stopped about 19 ms later and the wake microphone
  reopened about 97 ms after teardown.
- Final state was `wake_owned` with no active session, no accepted-session
  `idle_timeout`, host error, duplicate/ignored end call, or alternate cleanup.
- The human explicitly confirmed there was no audible GPT reply after the
  accepted farewell.
- Durable evidence in `F065-live-acceptance.md` excludes raw/private audio,
  transcript text, credentials, provider payloads, tool arguments, and call
  identities.

CODING_PASS: F065

# F109 fast coding evidence

## Scope

- Promoted the accepted same-session Mandarin Realtime acknowledgement to the
  default for every ordinary Realtime-backend wake.
- Kept browser input disabled until acknowledgement response completion and
  playback completion, then continued the same session for ordinary answers,
  tools, follow-ups, barge-in, and the native farewell.
- Restricted `REALTIME_ACKNOWLEDGEMENT_MODE` to `realtime` and `local`, with
  `realtime` as the default and `local` as the environment-only rollback.
- Left the classic pipeline acknowledgement path unchanged and retained
  bounded failure cleanup without playing a second fallback cue.
- Replaced externally visible experimental wording while retaining the
  privacy-safe lifecycle event names used by existing measurements.

## Verification

- Focused config, host, controller, and documentation suite: 77 passed.
- `node --check src/realtime_host/static/app.js`: passed.
- `git diff --check`: passed.
- Realtime fake smoke now exercises Realtime ACK gating followed by two turns,
  barge-in, calculator/weather/time/FX/stock tools, native farewell, teardown,
  and wake recovery: passed.
- Final `./init.sh`: passed with 438 project tests, 10 Mac frontend/fake
  sidecar tests, 25 Rust tests, dry-run, fake-backend, and Realtime fake smoke.

## Owner-authorized live evidence

- The first authorized run exposed a local deployment override:
  `.env` still selected `local` even though the checked-in production default
  was `realtime`. The private local setting was corrected and verified through
  the typed loader; it remains excluded from version control.
- In the corrected run, the owner heard the intended Mandarin Realtime ACK and
  confirmed that the ordinary answer was normal. Sanitized lifecycle evidence
  shows ACK response creation, playback start/stop, input enablement only after
  playback completion, ordinary tool-backed answering, and wake recovery.
- One earlier session in the same run reached `farewell_complete` after 1,456
  ms of browser-observable farewell playback, but the owner did not hear it.
  The owner's final session entered semantic farewell, then received a
  `realtime_error` 166 ms after `farewell_started`, before a farewell response
  was created; bounded cleanup restored wake ownership.
- The differing runs exposed a provider-ordering race: semantic tool
  completion sent an unnecessary `response.cancel` immediately before the
  farewell `response.create`. The semantic-tool path now waits for its natural
  `response.done`; only the transcription fallback cancels an active ordinary
  response. Focused host/controller/config tests pass after the correction.
- A separately authorized post-fix retry passed end to end. The owner heard
  both `嗯，我在，请说。` and `再见`; ordinary answers, tool use, follow-up, and
  interruption remained functional in the same session.
- Sanitized final timing after wake: configured-session readiness 1,802 ms,
  ACK response creation 1,993 ms, browser-observable ACK playback start 2,408
  ms, playback completion/input-enable 5,754 ms, and input ready 5,847 ms.
  Farewell response creation followed `farewell_started` by 194 ms, playback
  ran for 1,557 ms, normal `farewell_complete` cleanup followed playback stop,
  and local wake ownership reopened 93 ms later.
- The run ended `farewell_complete` with `recovered_to_wake=true`. No audio,
  transcript text, credentials, provider payloads, SDP, ICE, or private tool
  data were retained.

FAST_CODING_EVIDENCE: F109
CODING_PASS: F109

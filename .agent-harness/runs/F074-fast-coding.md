# F074 Fast Coding Evidence

Feature: F074 - Gate Realtime input behind an audible ready acknowledgement

FAST_CODING_EVIDENCE: F074

## Implemented contract

- Confirmed wake now closes the Python wake microphone and queues the browser
  handoff before local acknowledgement playback.
- The browser disables the acquired `MediaStreamTrack` before `addTrack`.
- OpenAI `session.updated` records bounded handoff timing and emits
  `host_session_configured`; it no longer marks the session active.
- The coordinator enters `host_ready` only after transport connection, session
  creation, and configuration acknowledgement.
- Python plays the existing acknowledgement only in `host_ready`, then queues
  one session-scoped `enable_input` command.
- The browser enables the active track and emits `host_connected`, which is now
  the exact `input_ready` boundary.
- Early, duplicate, stale, and pre-ready user-turn events fail closed. Startup,
  acknowledgement, input-ready timeout, error, Ctrl+C, and ordinary cleanup
  retain browser-media-before-wake recovery.

## External behavior verification

- OpenAI Realtime session lifecycle documentation states that the server emits
  `session.updated` after applying a client `session.update`:
  <https://developers.openai.com/api/docs/guides/realtime-conversations#session-lifecycle-events>
- The W3C Media Capture and Streams specification states that a disabled audio
  `MediaStreamTrack` supplies zero-information-content/silence to its consumer:
  <https://www.w3.org/TR/mediacapture-streams/>
- MDN documents `MediaStreamTrack.enabled=false` as producing empty audio
  frames whose samples are zero:
  <https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/enabled>

## Verification

```text
node --check src/realtime_host/static/app.js
python3 -m unittest discover -s tests -p 'test_*.py'
Ran 346 tests ... OK
python3 -m src.realtime.fake_smoke
Realtime fake smoke: ... connected=true ... recovered_to_wake=true
./init.sh
project recovery verification passed
```

Focused coverage verifies handoff-before-ack ordering, configured-session
readiness, track-disable ordering, one-shot input enablement, early/duplicate
readiness rejection, pre-ready activity rejection, acknowledgement failure,
input-ready timeout, updated RT001 version 6 timing/oracles, privacy
sanitization, and normal two-turn/interruption/cleanup behavior.

## Pending acceptance evidence

The feature remains `in_progress`. A user-led built-in microphone/speaker run
must still prove that no `host_speech_started` occurs before input readiness,
speech begun after “在呢” receives an audible response, and final cleanup
restores wake ownership. Separate cold-start evaluation must run only after
that live evidence is recorded.

CODING_PASS: F074

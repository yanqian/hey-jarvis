# F086 Live Attempt 2

LIVE_USER_AUTHORIZED: F086
LIVE_TECHNICAL_RESULT: PASS
LIVE_USER_AUDIBLE_CONFIRMATION: PASS
LIVE_PASS: F086

## Scope

The user unlocked the Apple Silicon Mac and continued the previously
authorized built-in-microphone/speaker Realtime trial. The run used the
isolated Tauri app, its bundled Python sidecar, and the spike-local ignored
`.env`. Evidence remains restricted to allowlisted lifecycle and capture
metadata.

## Realtime and interruption evidence

- The sidecar was ready on attempt 0 at 77 ms.
- WKWebView acquired a 48 kHz track with `echoCancellation=true`; the
  advertised `all` mode remained unavailable and the required `true` fallback
  was applied.
- The peer connected, attached its remote audio track, opened the transport,
  and recorded `session_created`.
- A normal human turn recorded speech start/stop and entered response
  generation.
- The deliberate long-answer run recorded playback start at 95480 ms, human
  speech at 102640 ms with `during_playback=true`, cancellation of the old
  response at 102667 ms, the replacement response at 104605 ms, replacement
  playback at 105225 ms, and successful completion at 109101 ms.

## Reacquisition failure and correction

The first `Stop and reacquire` attempt released WebRTC but blocked in
PortAudio's synchronous `read`. The run was stopped normally and left no
residual process. The spike was corrected in scope:

- WKWebView now allows a 300 ms CoreAudio release window after stopping every
  media track.
- Python uses a callback-based capture event with a hard two-second timeout
  instead of an unbounded blocking read.
- Deterministic no-frame coverage requires bounded
  `reason=microphone_timeout` failure.

The corrected Python suite contains 10 tests and the app bundle rebuild
passes.

## Corrected cleanup evidence

A fresh short session connected and then ran `Stop and reacquire`:

- the UI returned to `Stopped · ready for another trial`;
- Python reacquisition reported `PASS · 1280 frames`;
- the sanitized report contained `media_released` with `reason=user_stop`;
- the report contained the bounded reacquisition result;
- externally terminating the now-windowless Tauri parent caused the parent
  monitor to remove the Python sidecar within the one-second observation
  window, with no manual sidecar kill.

All technical acceptance signals pass. The user explicitly confirmed hearing
the normal answer and the replacement answer for “三加三” after deliberate
interruption. This is the final user-led live PASS. F086 still requires a
separate cold-start evaluator before completion.

# F105 Fast Coding Evidence

FAST_CODING_EVIDENCE: F105

## Implementation

- Added a keyboard-accessible Smart Speaker Mode toggle to General settings.
  It defaults off, persists in a versioned non-secret preferences file, and
  explains battery impact plus the explicit Sleep, shutdown, and lid-close
  boundaries.
- Added an injectable native power policy that acquires exactly one
  process-owned `PreventUserIdleSystemSleep` assertion only when the setting is
  enabled and F104 reports `wake_listening`.
- The native backend calls `IOPMAssertionCreateWithName` and
  `IOPMAssertionRelease` directly. It does not spawn `caffeinate`, request a
  display-sleep assertion, or rely on an incidental Core Audio assertion.
- Assertion acquisition and release are idempotent. The shared stop/release
  path covers Settings, disabling the mode, unavailable listening, microphone
  denial, sidecar stop or crash, system sleep, tray quit, and app exit.
- Assertion diagnostics contain only bounded lifecycle event names, states,
  and release reasons. Backend errors are not copied into diagnostics or UI.

## Automated Verification

- `node --check app/src/main.js`: PASS.
- `python3 -m unittest tests/test_mac_app_shell.py`: PASS (15 tests).
- `cargo test --locked --manifest-path app/src-tauri/Cargo.toml --quiet`: PASS
  (23 tests), including injected-backend gating, idempotent release, failed
  acquisition, and preference persistence/fail-closed coverage.
- Final `./init.sh`: PASS with 424 project tests, ten Mac frontend/sidecar
  tests, 23 Rust tests, Harness verification, and all fake smoke paths.

## Pending Joint Target-Mac Acceptance

- Inspect the running app with `pmset -g assertions` and process inspection to
  confirm one Hey Jarvis idle-system-sleep assertion, no display-sleep
  assertion, and no `caffeinate` child process.
- Let the display turn off and lock the Mac beyond its configured idle-sleep
  deadline, then complete wake acknowledgement, question/answer, and end-phrase
  voice loops.
- Confirm immediately after Settings, disable, simulated sidecar failure, and
  app quit that the Hey Jarvis assertion is absent.
- Do not mark F105 done or write evaluator approval until these target-Mac
  checks pass and a separate cold-start Evaluator accepts the complete evidence.

## First Target-Mac Lock Trial Failure

- Smart Speaker Mode acquired `Hey Jarvis Smart Speaker Mode` as one
  `PreventUserIdleSystemSleep` assertion; `pmset` showed no Hey Jarvis display
  assertion and process inspection showed no `caffeinate`.
- After the configured one-minute idle-sleep deadline, the user's locked-screen
  wake attempt produced `wake_listening -> busy`. The policy released the
  assertion for `voice_availability`; 17 ms later native diagnostics recorded
  `system_will_sleep`, followed by deterministic sidecar shutdown. No
  acknowledgement was audible.
- Root cause: the real wake was detected, but `busy` is the conversation
  handoff state and the original policy incorrectly treated it as a release
  boundary. An already-expired system idle timer could therefore sleep the Mac
  between wake detection and acknowledgement.
- Correction: only `wake_listening` may acquire an assertion, while an existing
  assertion remains held through its resulting `busy` conversation. Entering
  `busy` without first holding an assertion cannot acquire one. A repeat locked
  voice loop remains required.

## Repeat Lock Trial: Power Fix Passed, WebKit Handoff Failed

- The corrected build held the same Hey Jarvis idle-system-sleep assertion for
  more than two minutes, including throughout `wake_listening -> busy`; no new
  `system_will_sleep` event occurred, the sidecar remained alive, display-sleep
  prevention stayed zero, and no `caffeinate` process existed.
- The privacy-safe coordinator report proves local wake confirmation at
  `5792828050`, command delivery at `5792828171`, and browser microphone request
  at `5792828354`. WKWebView microphone acquisition did not complete until
  `5792841795`: 13,443 ms after request. Total browser readiness was 16,133 ms.
- ACK started only at `5792844515`, after transport and session configuration.
  The user heard it around opening the Mac and could not attribute it to the
  locked or unlocked state. No usable question reached the active input; the
  session stopped on the existing 60-second idle timeout and restored wake
  ownership.
- Root cause is now split cleanly: F105's native assertion policy survives the
  voice handoff, but the product Realtime path releases Python wake capture and
  requires a new WKWebView `getUserMedia` acquisition that macOS/WebKit does not
  complete promptly while locked. Power policy changes cannot repair that
  media-ownership boundary.

## Existing Chrome Realtime Lock A/B

- Reused the repository's unchanged `.venv/bin/python -m src.main --backend
  realtime` path, existing controller, wake detector, Realtime host JavaScript,
  and Chrome app-mode launcher. No experiment-specific product code was added.
- A test-only `caffeinate -i -w <cli-pid>` isolated browser media behavior from
  system idle sleep and exited automatically with the CLI. It is not proposed
  or accepted as product implementation.
- After more than the configured one-minute idle deadline while locked, Chrome
  recorded wake confirmation, requested its microphone 538 ms after handoff,
  and acquired it in 97 ms. Total browser readiness was 1,815 ms, versus the
  locked WKWebView trial's 13,443 ms microphone acquisition and 16,133 ms total.
- Chrome then recorded ACK completion, input readiness, one user speech turn,
  transcription, local-time tool completion, answer playback, a second speech
  turn, semantic end, clean host stop, and wake-microphone restoration. The
  technical lifecycle passed without unlocking; user audible confirmation is
  still required for complete acceptance.
- The A/B isolates the failure to the embedded WKWebView media host rather than
  the shared Python wake detector, coordinator, controller, Realtime protocol,
  or lock-screen power policy.

## WKWebView Warm-Media Correction and Passing Lock Trial

- Root cause refinement: WKWebView JavaScript, polling, WebRTC input, tool
  routing, and server events continued while locked, but media pipelines first
  created after lock were unreliable. Retaining only the input track reduced
  microphone acquisition from 13,443 ms to 5 ms, yet the first warm-input trial
  still deferred audible remote output until unlock because the `<audio>`
  element had no live source before lock.
- The bounded correction reuses the existing Enable gesture. In Smart Speaker
  Mode it retains the gesture-acquired microphone stream with its audio track
  disabled, attaches that live stream to the existing remote-audio element at
  zero volume, and starts playback before lock. A wake reuses the same live
  input track, swaps the already-playing element to the remote Realtime stream,
  and restores the configured output volume. Session stop disables the retained
  input and restores the zero-volume warm source; Settings and page lifecycle
  teardown stop both retained and active media immediately.
- In the successful owner-led locked trial, wake was confirmed at `5795225843`.
  WKWebView requested and acquired the retained microphone in 5 ms, connected
  transport, and reached total browser readiness in 2,019 ms. ACK completed,
  the spoken time question produced speech start/stop, transcription, the local
  time tool, and audible answer playback while still locked. The spoken end
  phrase produced `host_end_conversation_tool`, clean host stop, and wake
  microphone restoration at `5795242916`.
- The owner explicitly confirmed ACK, time answer, and end phrase all succeeded
  audibly while locked. `pmset` showed one Hey Jarvis
  `PreventUserIdleSystemSleep` assertion, no Hey Jarvis display-sleep
  assertion, and process inspection showed no product `caffeinate`.
- Focused verification after the correction: JavaScript syntax PASS; Mac shell
  tests PASS (15); Realtime Host tests PASS (41); Rust tests PASS (25). Final
  `./init.sh` PASS with Harness verification, 424 project tests, ten Mac
  frontend/fake-sidecar tests, 25 Rust tests, and all smoke paths. Independent
  evaluator review remains required before F105 may be marked done.

CODING_PASS: F105

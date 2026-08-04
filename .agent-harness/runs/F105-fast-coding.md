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

CODING_PASS: F105

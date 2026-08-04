# F104 Fast Coding Evidence

FAST_CODING_EVIDENCE: F104

## Implementation

- Added one bounded availability vocabulary (`ready`, `wake_listening`,
  `busy`, `resume_required`) derived from browser arming, coordinator state,
  and the actual local wake-microphone lease.
- Product-sidecar startup now reports `ready`, never `wake_listening`. Its
  bounded health reply publishes coordinator-derived voice availability; the
  native supervisor validates the allowlist and fails closed on unknown values,
  sidecar loss, startup failure, intentional stop, and failed recovery.
- Added a capability-protected, same-origin `/api/availability` endpoint for
  the loopback page. It carries only the canonical state and does not expand
  remote content into general native IPC.
- The Home page polls the bounded endpoint and releases browser media before
  showing `Resume required` when the runtime disappears. Conversation-specific
  Listening/Thinking/Speaking states remain richer than the generic native
  `Busy` state.
- Added a disabled menu-bar status item driven from the same native snapshot:
  Ready, Wake listening, Busy, or Resume required.

## Verification

- Focused Python sidecar tests: PASS (10 tests).
- `python3 -m unittest tests/test_mac_app_shell.py`: PASS (14 tests).
- `cargo test --manifest-path app/src-tauri/Cargo.toml`: PASS (18 tests),
  including invalid-availability and stopped-runtime fail-closed assertions.
- `node --check src/realtime_host/static/app.js`: PASS.
- Real Debug `.app` inspection through Computer Use: initial Home showed
  `READY`; after Enable and confirmed local microphone ownership it showed
  `WAKE LISTENING`; terminating only the product sidecar changed the still-open
  loopback page to `RESUME REQUIRED`; Settings showed `Not listening`; Done
  started a new runtime and returned to `READY` on a new loopback origin.
- The existing macOS sleep notification path synchronously calls
  `stop_sidecar(&runtime, "system_will_sleep")`; the same stopped snapshot and
  lost-origin path exercised above is therefore the fail-closed sleep outcome.
  Actual system sleep was not forced because it would interrupt the active
  evaluator session.
- Final `./init.sh`: PASS with 423 project tests, ten Mac sidecar tests,
  eighteen Rust tests, Harness verification, and all fake smoke paths.

CODING_PASS: F104

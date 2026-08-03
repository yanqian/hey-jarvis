# Run Record: F096 - stable runtime-to-Settings transition

## Summary

- Date: 2026-08-03
- Agent role: Provider-native Coding Agent through evaluator-gated fast work
- Feature: F096
- Result: coding complete; awaiting separate evaluator approval

## Implementation

- Removed the premature sidecar stop from `open_settings_window` so WKWebView can commit the bundled `tauri://localhost#settings-return` document while the outgoing loopback page is still available.
- Kept `enter_settings` as the Settings page's single intentional shutdown owner. The bundled page invokes it during load, preserving the truthful non-listening boundary without a timing delay.
- Added a focused source contract proving the native navigation helper does not stop the sidecar and the loaded Settings command still does.

## Verification

```bash
python3 -m unittest tests.test_mac_app_shell
cargo test --manifest-path app/src-tauri/Cargo.toml
npm run tauri -- build --debug --bundles app
./init.sh
```

- Focused Mac shell tests: 12 passed.
- Rust tests: 17 passed.
- Debug macOS app bundle rebuilt successfully.
- Final recovery: 411 project tests, ten Mac app/Python tests, seventeen Rust tests, dry-run smoke, fake-backend smoke, and Realtime fake smoke passed.
- Real Debug app: opening Settings from the main-window gear remained fully rendered after 2.5 seconds, beyond the former blanking window, and exposed `Not listening — the local voice runtime is stopped.`
- Real Debug app: Done returned to the wake-ready loopback page; `Command-,` then reopened the persistent bundled Settings page after the same 2.5-second check.
- No microphone control, permission prompt, credential mutation, or paid API action was used.

## Verdict

FAST_CODING_EVIDENCE: F096
CODING_PASS: F096

## Coding retry after evaluator rejection

The first evaluator correctly rejected F096 because the recovery-state
documentation test still hard-coded F095 as the current state. The retry
updates that contract to require the F096 in-progress and pending-evaluator
language. This is a test/state synchronization correction within F096; the
native implementation and real-app result are unchanged.

The corrected documentation test passes with 17 documentation checks, and a
fresh final `./init.sh` recovery run passes all project and smoke checks.

FAST_CODING_EVIDENCE: F096
CODING_PASS: F096

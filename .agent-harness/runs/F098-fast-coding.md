# F098 fast coding evidence

FAST_CODING_EVIDENCE: F098

- Confirmed the reported window is the current project Debug app, not the older `/Applications` copy.
- Root cause: native Settings navigation could reuse the exact bundled `#settings-return` URL while the document had been mutated to show `Returning to Jarvis`, allowing WKWebView to treat the request as a no-op.
- Added a monotonically increasing, process-local `settings-request` query token before the existing fragment so each native Settings entry loads a fresh bundled document.
- Preserved `enter_settings` as the sole intentional sidecar-stop boundary and made no credential, microphone, or paid API changes.
- Added a source contract for the token, atomic increment, and query-before-fragment ordering.
- Focused Python contracts, JavaScript syntax, Rust formatting, and all 17 Rust tests pass.
- Rebuilt the real Debug `.app` and reproduced the defect's exact starting state through accessibility inspection: `tauri://localhost#settings-return` retained the `Returning to Jarvis` DOM.
- Relaunched with the repository-local fake sidecar (no microphone, credential, or network use), activated Done to show the transition, then pressed Command-,. The window immediately rendered the Settings shell at `tauri://localhost?settings-request=1#settings-return`; a second Command-, rendered Settings at `settings-request=2`, proving successive requests do not reuse the mutated document.
- The first evaluator attempt correctly rejected the recovery state because `tests/test_documentation.py` still hard-coded the prior “no feature in progress” state. The recovery contract now reads F098 lifecycle state and checks the active or evaluator-completed progress wording accordingly; F098 was returned to `in_progress` for a clean retry.

CODING_PASS: F098

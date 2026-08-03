# Run Record: F095 fast coding

FAST_CODING_EVIDENCE: F095
CODING_PASS: F095

## Scope

- Replaced the bootstrap engineering/setup card with a dedicated modern
  Settings presentation organized as General, API Keys, Microphone, Privacy &
  Diagnostics, and About.
- Unified the conversation gear, tray Settings item, and standard macOS `⌘,`
  accelerator through one native settings helper.
- Preserved non-listening entry, Keychain add/replace/delete, durable
  microphone permission recovery, local readiness checks, support export,
  confirmed diagnostics clear, and explicit restart-and-return behavior.
- Kept credential values, raw audio, transcripts, provider bodies, protocol
  fields, session identifiers, and internal paths out of the presentation.

## Verification

- `npm run test:frontend`
- `python3 -m unittest tests.test_mac_app_shell`
- `cargo fmt --manifest-path app/src-tauri/Cargo.toml -- --check`
- `cargo test --manifest-path app/src-tauri/Cargo.toml` (17 passed)
- `npm test` (10 sidecar tests and 17 Rust tests passed)
- `python3 -m unittest tests.test_mac_app_shell tests.test_documentation` (29 passed)
- `npm run build -- --bundles app --debug`
- Browser visual inspection of every Settings navigation panel and privacy-safe
  content with no horizontal overflow at the inspected layout width.

Full `./init.sh` recovery verification follows this record. Independent
Evaluator evidence is intentionally not claimed here.

The first full recovery run reached 411 project tests and found only a
line-wrapping-sensitive progress assertion. The assertion was normalized to
the existing documentation-test convention before the final recovery retry;
no product behavior or acceptance scope was weakened.

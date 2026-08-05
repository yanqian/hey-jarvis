# F118 fast coding evidence

FAST_CODING_EVIDENCE: F118

CODING_PASS: F118

## Scope

- Added a schema-v2 `app_language` preference with bounded `en` / `zh-CN`
  validation, schema-v1 Smart Speaker migration, macOS preferred-language
  initialization, and secret-free persistence.
- Added exactly two General choices (`English` and `简体中文`) and complete
  English/Simplified-Chinese catalogs for the Settings shell, Resume and
  returning states, dynamic status/error text, the loopback interaction page,
  accessibility labels, native menus, Settings titles, and secure credential
  prompts.
- Language changes update the current WebView and native menu objects
  immediately. The loopback page reads the bounded preference through a local
  authenticated endpoint on its existing availability poll; no sidecar stop,
  restart, media release, conversation mutation, or power-policy change occurs.
- Added the new loopback catalog to frozen-sidecar packaging.

## Verification

- JavaScript syntax checks for both WebViews and catalogs: pass.
- Focused Mac shell, packaging, preference migration, native catalog, and
  no-restart language-endpoint tests: pass.
- `cargo test --manifest-path app/src-tauri/Cargo.toml`: 30 passed.
- `npm run tauri -- build --debug`: pass; rebuilt executable copied into the
  existing local Debug app bundle solely for visual inspection.
- `./init.sh`: pass with 460 project tests, 11 Mac frontend/fake-sidecar tests,
  30 Rust tests, dry-run, fake-backend smoke, and Realtime fake smoke.
- `git diff --check`: pass.
- Native Debug app inspection: pass in English and Simplified Chinese at the
  ordinary/compact window and fullscreen; every Settings panel was inspected
  in Chinese. See `F118-visual-acceptance.md`.

## Safety boundaries

- No network or paid API request, credential mutation, microphone request,
  speaker playback, diagnostic deletion, or conversation start was used.
- The temporary visual-QA language selection was restored to English.

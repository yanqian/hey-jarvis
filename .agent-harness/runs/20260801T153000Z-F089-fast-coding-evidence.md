# F089 fast coding evidence

Date: 2026-08-01
Feature: F089 - Add BYOK Keychain setup and first-run recovery

FAST_CODING_EVIDENCE: F089
CODING_PASS: F089

## Implemented scope

- Added native macOS Keychain storage for the required OpenAI key and optional
  Finnhub key, including add, replace, configured-status, retrieval for native
  bootstrap, and deletion behavior without exposing values to the WebView.
- Added versioned non-secret onboarding state and first-run disclosures for
  local wake listening, OpenAI audio boundaries, user-paid API usage, private
  diagnostics, and quit behavior.
- Added fail-closed Settings and recovery states for missing/invalid/locked
  credentials, microphone denial, unavailable input, readiness/startup errors,
  and returning-user diagnostics.
- Added a bounded private per-launch native-to-Python credential bootstrap;
  credentials do not use frontend JavaScript, URLs, argv, process listings,
  Application Support state, diagnostics, or public protocol messages.
- Added explicit runtime-to-Settings recovery, non-listening Settings lifecycle,
  development Python 3.12 selection, and stable return to the runtime Arm page.
- Made the loopback capability bootstrap compatible with the bundled Tauri
  origin using an HttpOnly, SameSite=Lax cookie while retaining one-time lease,
  loopback, Host, Origin, and session checks.

## Automated verification

- `node --check app/src/main.js`: pass.
- `node --check src/realtime_host/static/app.js`: pass.
- `python3 -m unittest tests.test_mac_app_shell`: 10 passed.
- `cargo test --manifest-path app/src-tauri/Cargo.toml`: 11 passed.
- `./init.sh`: pass outside the filesystem sandbox so the loopback capability
  test could bind a temporary localhost port. The run included 391 project
  tests, 9 Mac app frontend/fake-sidecar tests, 11 Rust tests, dry-run smoke,
  fake-backend smoke, and Realtime fake smoke.
- `git diff --check`: pass.

No real credential, raw audio, or transcript was committed or written to this
evidence.

## Target-Mac verification

The user-operated clean first-run/configuration path, real TCC denial and
re-enable path, Settings lifecycle, runtime startup, Arm, multi-turn follow-up,
barge-in, end phrase, and Python wake-microphone recovery are recorded in
`.agent-harness/runs/20260801T150441Z-F089-live-acceptance.md`.

This file records coding evidence only. A separate cold-start Evaluator Agent
must decide acceptance and is the only phase authorized to record `EVAL_PASS`,
set `passes=true`, or set `status=done`.

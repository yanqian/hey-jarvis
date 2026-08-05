# Run Record: F114 - non-disruptive Settings lifecycle

## Summary

- Date: 2026-08-05
- Agent role: provider-native Coding Agent after work-fast handoff
- Feature: F114
- Result: coding pass; independent evaluation pending
- Starting commit: `daec7f3`

## Implementation

- Replaced in-place Settings navigation with one native `settings` WebView
  window. Gear, tray, menu, and command entry focus the existing window or
  create it on a background thread; ordinary entry no longer stops Python,
  releases retained media, or changes the main runtime document.
- Settings polls only the bounded availability enum and renders truthful
  `ready`, `wake_listening`, `busy`, or `resume_required` state. It does not
  receive session content or credentials. Done closes only the Settings
  window.
- General, About, diagnostics, and Smart Speaker preference inspection remain
  runtime-neutral. Successful credential replacement/deletion and an explicit
  microphone check are runtime-affecting: they use F113 safe shutdown and keep
  a focused Resume action visible until real `wake_listening` is observed.
- Bounded microphone permission probing now times out after 15 seconds and
  immediately stops a stream that resolves after the timeout.
- Removed the loopback page's stale `openAppSettings()` cleanup, which had
  independently disarmed the runtime and released retained microphone media
  before native Settings interception.

## Automated verification

- JavaScript syntax and Rust formatting checks passed.
- 52 focused frontend, documentation, controller, coordinator, and sidecar
  tests passed; 27 native Rust tests passed.
- Final `./init.sh` passed: 456 project tests, 11 Mac app tests, 27 Rust tests,
  dry-run, fake-backend, and Realtime fake smoke all passed.
- `git diff --check` passed.

## Target-Mac result

- With Smart Speaker Mode enabled and truthful `wake_listening`, repeated gear
  and Command-, entry focused one Settings window. Python remained PID 87782
  with session `session-b63348070cf583adb541bed08a9a40b1`, the main page stayed
  on the runtime, and the native Smart Speaker assertion remained active.
- Settings displayed `Wake listening remains active while Settings is open`.
  Done dismissed only Settings; the main window still showed Wake listening.
- An explicit microphone check exercised the runtime-affecting path. Python
  recorded `shutdown_requested` then `process_stopped` about 220 ms later;
  Settings truthfully showed Resume required and exposed the Resume action.
- The DiagnosticReports baseline remained unchanged at six Python reports,
  with the latest `Python-2026-08-05-121108.ips`; no new matching crash report
  or Python-exit system dialog appeared.

FAST_CODING_EVIDENCE: F114
CODING_PASS: F114

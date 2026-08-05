# Run Record: F106 - bounded sleep recovery coding

## Summary

- Date: 20260804T144807Z
- Agent role: provider-native Coding Agent after work-fast handoff
- Feature: F106
- Result: coding pass; target-Mac acceptance and independent evaluation pending
- Starting commit: `7168e33`

## Root Cause Evidence

The app-owned lifecycle diagnostics contain repeated ordered sequences where
`system_will_sleep` is immediately followed by `sidecar_stopped`, while the
later `system_did_wake` event has no matching restart. This matches the prior
native implementation: the sleep notification synchronously stopped the
sidecar and the wake notification only recorded a diagnostic event. There is
no product 30-minute expiry constant on this path.

The recovery page's Settings button relied on an asynchronous JavaScript
handler reaching `window.location.assign` after cleanup. The user-observed
non-response is corrected by making the gear itself a declarative
`hey-jarvis://settings/open` link while retaining best-effort media cleanup.

## Implementation

- Added a generation-scoped `SleepRecoveryPolicy` that records only whether
  Smart Speaker Mode was enabled and genuinely active, permits one automatic
  wake attempt, rejects stale timeout work, and cancels on intentional stops.
- Moved sleep sidecar teardown and wake restart work off the macOS notification
  callback. Browser navigation is dispatched to the main thread.
- Added a 15-second readiness gate. Success is recorded only when the existing
  truthful availability reaches `wake_listening`; failure remains
  non-listening and opens a focused local Resume surface.
- Added an explicit native Resume command and a recovery WebView flow. The
  loopback host tries safe browser re-arming once and exposes a gesture-backed
  Resume action if WKWebView refuses automatic microphone/audio restoration.
- Preserved no-pre-wake paid activity: recovery starts only the local sidecar,
  loopback host, retained-disabled microphone posture, and wake detector.
- Replaced the runtime gear button with a declarative custom-scheme link so
  Settings remains reachable in the paused state.
- Added automated policy, stale-generation, UI, navigation, documentation, and
  manual-acceptance contracts.

## Verification

```text
node --check app/src/main.js
node --check src/realtime_host/static/app.js
cargo test --manifest-path app/src-tauri/Cargo.toml
  27 passed
npm test  # app/
  10 sidecar tests and 27 Rust tests passed
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
  454 passed
npm run build  # app/
  release application built successfully
./init.sh
  project recovery verification passed
```

The first full Python run inside the restricted sandbox was rejected only when
the loopback fixture tried to bind `127.0.0.1`; the same suite passed outside
that socket restriction. No live OpenAI request, paid Realtime session, raw
audio, transcript, answer, credential, SDP, ICE, or provider body was used or
retained by this coding run.

## Remaining Acceptance

The owner must run M106 on the target Mac: explicitly sleep and wake from a
genuinely active Smart Speaker session, confirm either bounded automatic
recovery or the clickable Resume fallback, verify Settings responds, then
complete one wake/question/farewell/next-wake loop. Only after that evidence
may a separate cold-start Evaluator Agent accept F106.

FAST_CODING_EVIDENCE: F106
CODING_PASS: F106

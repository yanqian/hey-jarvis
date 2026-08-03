# Run Record: F097 - Settings interaction and compact-layout polish

## Summary

- Date: 2026-08-03
- Agent role: Provider-native Coding Agent through evaluator-gated fast work
- Feature: F097
- Result: coding complete; awaiting separate evaluator approval

## Implementation

- Done now hides Settings on the next rendered frame and shows a bundled, privacy-safe `Returning to Jarvis` startup surface while `restart_sidecar` performs the real cold start.
- A restart failure restores Settings, shows actionable recovery guidance, and returns keyboard focus to Done.
- Settings waits for a committed two-frame paint before `enter_settings` stops the outgoing loopback sidecar, closing an intermittent blank-WebView race without a fixed time delay.
- Add/Replace key labels no longer use ellipses.
- Settings action buttons now use a 12px, weight-500 type treatment and quieter semantic surfaces.
- API-key actions wrap into a full-width responsive row at 700px and below; each action can flex without clipping Delete.

## Verification

```bash
node --check app/src/main.js
python3 -m unittest tests.test_mac_app_shell tests.test_documentation
cd app && npm test
cd app && npm run tauri -- build --debug --bundles app
./init.sh
```

- Focused frontend/documentation tests: 29 passed.
- Mac sidecar tests: 10 passed; Rust tests: 17 passed.
- Final recovery: 411 project tests and all dry-run, fake-backend, and Realtime fake smoke paths passed.
- Real Debug app remained rendered three seconds after opening Settings with the committed-paint boundary.
- At the configured 560px window, API Keys rendered Replace key and Delete for both providers without clipping; the responsive rule covers the supported 480px minimum.
- Real Done flow replaced Settings with the bundled startup surface and ultimately reached the wake-ready loopback page. The development sidecar cold start in this observation was about 30 seconds, confirming the delay is runtime/model startup rather than a settings save.
- No credential button, microphone control, permission prompt, or paid API action was used.

## Verdict

FAST_CODING_EVIDENCE: F097
CODING_PASS: F097

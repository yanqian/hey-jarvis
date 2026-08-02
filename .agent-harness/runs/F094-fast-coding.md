# F094 Fast Coding Evidence

FAST_CODING_EVIDENCE: F094
CODING_PASS: F094

## Scope

- Replaced the production loopback WKWebView engineering dashboard with a focused Hey Jarvis interaction surface.
- Added truthful `ready`, `wake-ready`, `connecting`, `listening`, `thinking`, `speaking`, `stopping`, and `error` presentation states driven by existing media and Realtime events.
- Removed ordinary-surface audio settings, event logs, and the long-answer test control without changing the underlying diagnostic event collection or fixture command behavior.
- Preserved explicit user media arming, disabled-track input enablement, end-session request, settings media release, playback events, semantic ending, and wake recovery.
- Added a CSS-only orb/wave visual, visible keyboard focus, semantic live status, responsive layouts, and reduced-motion behavior with no new dependency or copied asset.
- Resized the main Tauri window from 760x640 to 560x600 with a 480x520 minimum.
- Updated product and test documentation for the renamed `Enable voice assistant` control.

## Verification

- `node --check src/realtime_host/static/app.js` passed.
- `python3 -m unittest tests.test_realtime_host` passed with 39 tests using approved localhost test binding.
- `python3 -m unittest tests.test_mac_app_shell tests.test_documentation` passed with 27 tests.
- Browser visual inspection at 560x600 confirmed one visible initial primary action, a hidden inactive end-session action, legible hierarchy, and no horizontal or vertical overflow.
- Browser responsive inspection at the supported 480x520 minimum confirmed `scrollWidth == clientWidth` and `scrollHeight == clientHeight`.
- Visual inspection found and fixed an author-CSS override of native `[hidden]`; the corrected end-session action is not visible before a session.
- Final `./init.sh` passed with 409 project tests, 10 Mac app frontend/Python tests, 17 Rust tests, dry-run and fake-backend smokes, and the Realtime fake smoke.

## Boundaries

- No live microphone, OpenAI request, paid activity, signing, packaging, or external network access was used.
- F095 settings-window and credential-sensitive navigation work was not implemented.
- Existing untracked real-test logs under `tmp/` were not modified or added to evidence.

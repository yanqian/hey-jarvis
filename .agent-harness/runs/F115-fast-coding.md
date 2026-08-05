# Run Record: F115 - Settings information hierarchy

## Summary

- Date: 2026-08-05
- Agent role: provider-native Coding Agent after work-fast handoff
- Feature: F115
- Result: coding pass; independent evaluation pending
- Starting commit: `932a7ac`

## Implementation

- Replaced the duplicate page summary plus status sentence with one compact,
  atomic live Voice status component containing a non-color state label and a
  short supporting detail.
- Split General semantically into Assistant setup and Smart Speaker Mode.
  Readiness, start, and readiness-check controls now stay together; the mode
  toggle, current mode state, and sleep/wake explanation stay together.
- Kept the detailed battery, explicit Sleep, lid-close, bounded wake recovery,
  and shutdown behavior in an accessible native disclosure named `How sleep
  and wake work`.
- Kept `Local until you wake it` as a separate privacy note.
- After owner visual feedback, removed the two outer group cards. The final
  hierarchy uses section headings, whitespace, and one quiet divider, with
  borders only on the actionable readiness and Smart Speaker control cards.
- Preserved every existing action ID and JavaScript/native behavior.

## Verification

- `node --check app/src/main.js` passed.
- 33 focused Mac shell and documentation tests passed.
- DOM/source contracts prove exactly one live-status component, correct action
  ownership, accessible disclosure copy, no outer group border/background, and
  existing responsive/focus/reduced-motion behavior.
- `npm run tauri -- build --debug --bundles app` produced the inspected Debug
  application.
- Final `./init.sh` passed with 456 project tests, 11 Mac app tests, 27 Rust
  tests, and dry-run, fake-backend, and Realtime fake smoke paths.
- `git diff --check` passed.

## Local visual result

- At the regular Settings size, one Voice status row replaced the repeated
  availability copy and the two General sections were immediately separable.
- At the compact supported size, buttons wrapped without overlap and the
  Smart Speaker state remained readable.
- The disclosure exposed correct collapsed/expanded accessibility state and
  its full safety text.
- Final owner-directed revision removed nested outer frames and retained only
  single-layer actionable cards.
- No microphone check, credential mutation, or paid conversation was invoked.

FAST_CODING_EVIDENCE: F115
CODING_PASS: F115

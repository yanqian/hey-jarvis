# F116 fast coding evidence

FAST_CODING_EVIDENCE: F116

CODING_PASS: F116

## Scope

- Removed the redundant `ASSISTANT SETUP` and `POWER & WAKE` eyebrow labels while retaining semantic h3 headings and descriptions.
- Removed the setup action-row divider so readiness and its actions remain one uninterrupted group.
- Kept the existing divider between Setup and Smart Speaker Mode.
- Removed the divider above the sleep/wake disclosure and added a standalone divider immediately above the local privacy note.
- Added Settings-only wide-and-tall viewport top padding for native fullscreen visibility.
- Runtime JavaScript, native commands, IDs, control order, and other Settings panels were unchanged.

## Verification

- `node --check app/src/main.js`: pass.
- `python3 -m unittest tests.test_mac_app_shell`: 16 passed.
- `git diff --check`: pass.
- `npm run build`: pass.
- `npm run tauri -- build --debug`: pass.
- Native Debug app Settings inspection: pass at ordinary and fullscreen sizes; see `F116-visual-acceptance.md` and `F116-fullscreen-acceptance.jpeg`.

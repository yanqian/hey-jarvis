# F121 fast coding evidence

FAST_CODING_EVIDENCE: F121

CODING_PASS: F121

## Scope

- Replaced the two visible language labels and two explanations with one
  semantic `Language` heading and one sentence preserving immediate-interface
  and next-wake fixed-cue timing.
- Kept the existing two-option selector aligned beside that copy at regular
  widths and stacked below it under 700 pixels.
- Connected the selector to `language-title` and `language-description` for
  screen-reader naming and description.
- Updated the Simplified Chinese catalog with the matching combined sentence.

## Verification

- `node --check app/src/main.js`: pass.
- `node --check app/src/i18n.js`: pass.
- `python3 -m unittest tests.test_mac_app_shell`: 17 passed.
- Current-source `npm run tauri -- build --debug`: pass.
- Local same-source WebView preview: English and Simplified Chinese pass at
  wide/default and 560x600 compact viewports; headings, descriptions, ARIA
  names, selector wrapping, dividers, and adjacent groups remained intact.
- Rebuilt native Debug app: English and Simplified Chinese pass in the 560x600
  compact window and macOS full screen. Accessibility exposes one localized
  heading, one localized description, and one language-named popup in each
  locale; screenshots show clean stacking/alignment without clipping.
- Final `./init.sh`: pass with 460 project tests, 11 Mac frontend/fake-sidecar
  tests, 30 Rust tests, dry-run, fake-backend smoke, and Realtime fake smoke.
- `git diff --check`: pass.

## Safety

- No runtime control, microphone, credential, speaker, network, or paid API was
  used. The language preference was switched only for native visual inspection,
  then restored to English; the app was returned to compact mode and closed.
  Temporary local preview files and servers were removed after inspection.

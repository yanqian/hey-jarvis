# F101 Fast Coding Evidence

FAST_CODING_EVIDENCE: F101

## Implementation

- Replaced the face-like icon with a deterministic SVG master containing the
  approved deep green-charcoal tile, mint capital `J`, original short rounded
  upper platform, separated listening orb, and three warm-white voice bars.
- Added `scripts/generate_macos_icons.sh`, which uses the installed Tauri icon
  generator directly from SVG to emit exact 16, 32, 64, 128, 256, 512, and
  1024-pixel iconset members plus Tauri PNGs and `icon.icns`.
- Added a separate black-on-transparent menu-bar SVG and direct 18/36-pixel
  outputs. Native tray construction embeds the 36-pixel asset and calls
  `.icon_as_template(true)` so macOS owns light/dark appearance.
- Kept the tray menu handlers for Show, Settings, and Quit unchanged.

## Verification

- `python3 -m unittest tests.test_mac_app_icons tests.test_internal_macos_release tests.test_mac_app_shell`: PASS (23 tests).
- `cargo test --manifest-path app/src-tauri/Cargo.toml`: PASS (17 tests).
- `npm run tauri -- build --debug --bundles app`: PASS; the Debug app bundle
  built and launched as `Hey Jarvis` without credential, microphone, or paid
  API interaction.
- `./init.sh`: PASS with Harness checks, 417 project tests, ten Mac app
  frontend/sidecar tests, seventeen Rust tests, and all fake smoke paths.
- RGBA tests prove both menu-bar corners are transparent, dimensions are
  exactly 18x18 and 36x36, coverage is bounded, and every pixel with non-zero
  alpha has RGB channels at or below 8. Antialiasing therefore carries black
  color only and cannot expose a stored white edge under template rendering.
- `.agent-harness/runs/F101-icon-contact-sheet.png` preserves inspected app
  renders at 16/32/128/512 and template renders on light/dark backgrounds.
  Computer Use launched and inspected the real Debug app; SystemUIServer does
  not expose a capturable window through that interface, so menu-bar appearance
  is supported by the actual template-loading code path plus deterministic
  light/dark compositing rather than a claimed SystemUIServer screenshot.

CODING_PASS: F101

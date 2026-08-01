# F090 fast coding evidence

Date: 2026-08-01
Feature: F090 - Package a reproducible Python and wake-model runtime

FAST_CODING_EVIDENCE: F090
CODING_PASS: F090

## Implemented

- Added exact build/runtime locks, fixed model URLs and SHA-256 values, an
  audited TFLite-only openWakeWord runtime initializer, and an Apple Silicon
  PyInstaller onedir spec.
- Added a clean build entrypoint with Python 3.12/arm64 checks, constrained
  output paths, model hash enforcement, deterministic standard-library ZIP
  normalization, and no release dependence on system Python or the repository
  virtual environment.
- Added exhaustive artifact, nested-code, model, dependency/license, build
  input, size, architecture, linked-library, and SHA-256 manifests; Tauri
  bundles both the full onedir and its manifests/licenses.
- Added a frozen offline smoke using the real TFLite models plus deterministic
  microphone/OpenAI/calculator behavior, and packaging contract tests.
- Added explicit beta budgets and measured the onedir, complete unsigned app,
  unsigned DMG candidate, first post-build start, and immediate warm start.

## Verification

- Two normalized clean builds: byte-identical full artifact manifest.
- Frozen empty-environment model/fake smoke: pass from standalone onedir and
  from the `.app` resource path.
- Empty-stdin fail-closed and residual-process check: pass.
- `python3 -m unittest tests.test_macos_sidecar_packaging app.sidecar.tests.test_product_sidecar`: 11 passed.
- `cargo test --manifest-path app/src-tauri/Cargo.toml`: 11 passed.
- Unsigned release `.app` build with bundled onedir/manifests: pass.
- Unsigned compressed DMG candidate creation for measurement: pass.
- Final `./init.sh`: pass with 397 project tests, 9 Mac app Python tests, 11
  Rust tests, dry-run, fake-backend, and Realtime fake smoke.
- `git diff --check`: required before evaluator handoff.

Full build, reproducibility, inventory, lifecycle, and measurement evidence is
in `.agent-harness/runs/20260801T170000Z-F090-apple-silicon-packaging.md`.

This is coding evidence only. It does not mark F090 done and does not contain
an evaluator verdict; only the separate cold-start Evaluator Agent may do so.

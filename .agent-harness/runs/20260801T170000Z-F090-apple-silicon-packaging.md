# F090 Apple Silicon packaging evidence

Date: 2026-08-01
Feature: F090 - Package a reproducible Python and wake-model runtime
Platform: Apple Silicon, arm64, macOS 26.5, Python 3.12.13

## Clean build and model boundary

`./scripts/build_macos_sidecar.sh` created a new build environment rather than
using installed project packages as the artifact source. It installed only the
exact versions in the two dependency locks, installed openWakeWord 0.6.0
without its optional dependency metadata closure, downloaded exactly the three
TFLite files in `models.lock`, verified all three SHA-256 values, applied the
audited runtime-only package initializer, and built a PyInstaller 6.16.0 arm64
onedir.

The first clean attempt correctly stopped because the published openWakeWord
wheel did not contain model assets. That established that the repository
`.venv` models were prior downloads, not wheel content. Fixed release URLs and
hashes were then made durable rather than allowing runtime download.

The finished artifact contains no ONNX model, onnxruntime, SciPy, sklearn,
OpenAI SDK, WebRTC VAD, tests, or cache directories. The upstream TFLite
`model.py` and `utils.py` inference implementation is unchanged. The packaged
initializer avoids only eager imports for unused ONNX VAD and verifier
training, and exposes only the `hey_jarvis` model metadata.

## Reproducibility and inventory

An initial two-build comparison found exactly one differing file:
`_internal/base_library.zip`. Per-entry content and metadata were identical,
but PyInstaller emitted standard-library entries in dependency-graph iteration
order. `normalize_zip.py` now sorts those entries and fixes ZIP metadata.

Two subsequent clean builds produced byte-identical complete
`artifact-manifest.json` files:

```text
ae6018880656ef56d7707efc15b600988d62f02b0c31627d40ee1e66fd7f13b2
```

The inventory contains 82 nested-code destinations. Every Mach-O executable,
dylib, and extension reports only `arm64`; each entry records its deterministic
bundle-relative destination, linked libraries, mode, size, signing class, and
SHA-256. The generated dependency/license tree contains exact installed
versions, declared license metadata, 99 copied license/notice files with
hashes, and separate model/build/input-hash manifests. Those manifests and
licenses are bundled at `Contents/Resources/packaging-manifests`; the complete
onedir is bundled at `Contents/Resources/sidecar`.

## Offline behavior and lifecycle

The frozen executable was launched with:

```bash
env -i PATH=/usr/bin:/bin HOME=/tmp TMPDIR=/tmp \
  build/macos-sidecar/hey-jarvis-sidecar/hey-jarvis-sidecar --packaging-smoke
```

It loaded the real three-model TFLite `hey_jarvis` path and completed the
deterministic fake microphone, fake OpenAI, calculator, playback, and cleanup
flow. The same probe passed from inside the unsigned app bundle. Therefore the
runtime did not use a repository `.venv`, system Python packages, a Homebrew
executable path, a credential, or a model/network download.

Empty inherited stdin returned exit code 2, and a subsequent process-table
check found no `hey-jarvis-sidecar` process. Existing Rust supervision tests
also cover shutdown, bounded wait, forced termination, and missing sidecar.

## Measurements and budgets

The explicit portfolio-beta budgets and actual unsigned measurements are:

| Surface | Budget | Actual | Result |
| --- | ---: | ---: | --- |
| Sidecar onedir logical files | 180 MiB | 95,998,611 bytes | pass |
| Sidecar disk allocation | informational | 64,648 KiB | measured |
| Complete `.app` logical files | 250 MiB | 107,989,298 bytes | pass |
| Complete `.app` disk allocation | informational | 106,012 KiB | measured |
| Unsigned compressed DMG candidate | 150 MiB | 43,963,029 bytes | pass |
| First post-build frozen smoke | 30 s | 22.93 s wall; 11,156 ms in-process | pass |
| Immediate warm frozen smoke | 5 s | 0.19 s wall; 98 ms in-process | pass |

The first copy under the app resource path took 12.59 seconds wall and then
reported 115 ms in-process; its immediate rerun took 0.19 seconds wall. The
large first-run difference is honestly attributed only to pre-main OS/file
verification and cache effects, not to a measured internal substage.

The final unsigned DMG candidate SHA-256 was
`0ee0a9de0d688ea35beba663629e746bd2af71c4fa84b111cee65d34646aa650`.
It is measurement evidence only: F092 must rebuild, sign every nested item,
notarize, staple, and remeasure the distributable artifact.

No real credential, raw audio, transcript, or private runtime log was used or
recorded in this evidence.

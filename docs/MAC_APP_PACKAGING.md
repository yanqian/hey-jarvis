# Mac App Python packaging

F090 freezes the Apple Silicon product sidecar as a PyInstaller `onedir`
runtime. It is deliberately separate from Developer ID signing, notarization,
and the final DMG workflow, which remain F092 scope.

## Reproducible build

Run from the repository root on Apple Silicon macOS with Python 3.12:

```bash
./scripts/build_macos_sidecar.sh
```

`HEY_JARVIS_BUILD_PYTHON` may select another Python 3.12 executable. Build
output is allowed only below the repository `build/` directory or a path named
`/tmp/hey-jarvis-*`. The script creates a clean environment, installs the exact
build and runtime versions in `packaging/macos-sidecar/*.lock`, downloads only
the three TFLite assets in `models.lock`, verifies every model SHA-256, applies
the audited runtime-only openWakeWord initializer, builds an arm64 onedir, and
writes manifests under `build/macos-sidecar/manifests/`.

The runtime initializer removes upstream eager imports for optional ONNX VAD
and SciPy/scikit-learn verifier training. It does not change the upstream
`model.py` or `utils.py` inference implementation. The product default uses
TFLite, `WAKE_VAD_THRESHOLD` is unset, and recording WebRTC VAD remains disabled;
therefore ONNX, SciPy, scikit-learn, the optional WebRTC package, tests, caches,
and unused wake models are not shipped. The packaged smoke preloads the real
three-model TFLite path and runs the deterministic fake microphone/OpenAI/
calculator flow, providing behavior evidence for this removal.

The generated manifests are:

- `artifact-manifest.json`: relative destination, bytes, mode, type, SHA-256,
  and signing class for every file;
- `nested-code-manifest.json`: every executable, dylib, and extension plus
  architecture and linked libraries for bottom-up signing;
- `dependency-license-manifest.json` and `licenses/`: exact installed build and
  runtime distribution versions, declared licenses, copied license/notice
  files, and hashes;
- `model-manifest.json`: the exact three model destinations, sizes, and hashes;
- `build-manifest.json`: Python/platform provenance, manifest hashes, total
  logical bytes, and budget result.

PyInstaller's standard-library ZIP writes dependency-graph iteration order.
`normalize_zip.py` rewrites that ZIP in sorted order with fixed metadata. Two
fresh F090 builds must produce byte-identical `artifact-manifest.json` files;
the actual accepted comparison is retained in Harness run evidence.

## Offline and lifecycle probes

The following launches only the frozen runtime and its bundled models. The
empty environment proves it does not find a repository virtual environment,
Homebrew executable, system Python package, API key, or model download path:

```bash
env -i PATH=/usr/bin:/bin HOME=/tmp TMPDIR=/tmp \
  build/macos-sidecar/hey-jarvis-sidecar/hey-jarvis-sidecar --packaging-smoke
```

The probe preloads `hey_jarvis` through the bundled TFLite interpreter, then
runs the deterministic fake microphone, fake OpenAI, calculator, and cleanup
path. Ordinary execution remains the stdin/stdout product protocol. EOF before
or after supervision is fail-closed, and Rust owns the bounded stop/kill/wait
sequence. No packaging probe reads a real credential or opens the network.

## Portfolio beta budgets

These are measurement gates, not promises or arbitrary pruning targets:

- onedir logical bytes: at most 180 MiB;
- complete unsigned `.app` disk bytes: at most 250 MiB;
- compressed unsigned DMG candidate: at most 150 MiB;
- first post-build model/fake smoke: within the existing 30-second supervisor
  readiness boundary;
- immediate warm model/fake smoke: at most 5 seconds.

The accepted F090 run records actual sidecar, app, DMG-candidate, cold, and warm
measurements. A signed/notarized DMG can differ and will be measured again by
F092. No Intel/universal2 or final download-size claim is made.

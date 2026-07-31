# Tauri Realtime host capability spike

This is the isolated F086 architecture spike. It answers one question:

> Can Tauri 2's macOS WKWebView replace the accepted Chrome app-mode Realtime
> host while preserving microphone capture, built-in-speaker playback,
> interruption, media teardown, and Python microphone reacquisition?

Nothing below this directory is imported by `src/`, and the root product
runtime does not require Node, Rust, Tauri, this sidecar, or this spike. A pass
does not migrate the product.

## Boundaries

- Target: Apple Silicon macOS, Tauri 2, WKWebView.
- Frontend: static HTML/CSS/JavaScript owned by this spike.
- Native shell: Rust/Tauri window, tray, lifecycle, and sidecar supervision.
- Sidecar: spike-local Python service packaged as an app-bundled development
  runtime plus a Tauri external-binary launcher.
- Control: `127.0.0.1:8871` plus a cryptographically random per-launch token.
- Credential: `OPENAI_API_KEY` is read by Python from this directory's ignored
  `.env`; it is not sent to JavaScript, Rust commands, argv, logs, or reports.
- Evidence: lifecycle and capture settings only; no audio, SDP, transcript,
  answer, API key, tool argument, or provider body is retained.

The loopback shape is intentionally preserved for this first probe. Replacing
Chrome/WKWebView and replacing IPC in the same experiment would confound the
result.

## Prerequisites

Install Apple's Command Line Tools, Node/npm, and Rust/Cargo. The environment
used for F086 was:

```text
Apple Silicon macOS
Node 26
npm 11
Rust/Cargo 1.97
Python 3
```

The exact JavaScript and Rust dependency graph is locked by `package-lock.json`
and `src-tauri/Cargo.lock`. Python packages are bounded by `requirements.txt`.

## Setup

From this directory:

```bash
cp .env.example .env
# Edit only this spike-local .env and set OPENAI_API_KEY.
npm run setup
```

`npm run setup` creates `.venv`, installs the spike-local Python and npm
dependencies, and packages the Python service as the Apple Silicon Tauri
sidecar. It does not use the repository root `.venv` or import product code.

## Offline verification

```bash
npm test
npm run build:app
```

The checks cover:

- no imports or source-path references to product `src/`;
- private spike identity and sidecar boundary;
- frontend syntax;
- Python configuration, credential containment, multipart SDP/session shape,
  event allowlist, privacy, cleanup report, and fake microphone reacquisition;
- Rust random per-launch token and loopback configuration;
- reproducible Python sidecar packaging;
- Tauri macOS app compilation.

Offline checks do not prove WKWebView microphone or WebRTC behavior.

## Live target-Mac trial

Live execution uses a real OpenAI Realtime session, microphone, and speakers,
may incur cost, and must be explicitly authorized.

```bash
npm run dev
```

Then:

1. Select the Mac built-in microphone and built-in speakers; do not use
   headphones.
2. Click **Start WKWebView session** and grant the app microphone permission.
3. Confirm actual `echoCancellation`, `noiseSuppression`,
   `autoGainControl`, sample rate, and channel count appear.
4. Speak one normal question and hear its answer.
5. Click **Play long answer**.
6. While it is audibly speaking, interrupt naturally with
   “Stop. What is two plus two?”
7. Confirm the old answer stops and the interruption receives a response.
8. Click **Stop and reacquire**.
9. Require `Python reacquisition` to show `PASS`.
10. Refresh the sanitized report and preserve it in the F086 run evidence.

## Verdict

F086 passes only when offline checks, Tauri app build, the user-led live trial,
and a separate cold-start evaluator all pass. A failed live result is still a
useful and honest architecture result; do not tune the production runtime or
replace Chrome to make this spike appear successful.

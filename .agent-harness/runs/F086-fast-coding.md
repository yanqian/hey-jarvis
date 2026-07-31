# F086 Fast Coding Evidence

FAST_CODING_EVIDENCE: F086
CODING_PASS: F086

## Result

The isolated Tauri/WKWebView capability host is implemented and its offline,
bundle, startup, and shutdown checks pass. The explicitly authorized
built-in-microphone/speaker Realtime trial and separate evaluator approval
remain pending, so F086 stays `in_progress` and this record does not claim
`EVAL_PASS`.

## Isolation and implementation

- Every spike-owned source file, lockfile, script, test, manifest, capability,
  and document lives below `spikes/tauri_realtime/`.
- The root product does not import or invoke the spike. A dependency-free
  static check rejects product-source imports and verifies the private bundle
  identity and external-sidecar boundary.
- Tauri 2 owns the WKWebView window, tray, random per-launch capability token,
  sidecar lifecycle, and bounded commands.
- The spike-local Python service binds only `127.0.0.1:8871`, requires the
  per-launch token, owns the OpenAI credential, creates the unified Realtime
  WebRTC call, records allowlisted metadata only, and provides a microphone
  reacquisition probe.
- JavaScript requests and reports the actual WKWebView audio-capture settings,
  owns the WebRTC media lifecycle, supports a deliberate long-answer
  interruption trial, releases every track before Python reacquisition, and
  never receives the API key.

## Packaging finding

The first PyInstaller `--onefile` bundle launched successfully but Tauri's
shutdown killed only the bootloader parent and left its extracted child
orphaned. That shape was rejected. The accepted spike packaging uses a
PyInstaller `--onedir` runtime inside the app resources plus a minimal tracked
Tauri external-binary launcher. The rebuilt app reported the sidecar ready on
attempt 0 at 77 ms. After normal app quit, a process-table check found no
Tauri or Python sidecar process.

## Verification

- `npm test` passed the isolation check, JavaScript syntax check, 10 Python
  tests, 2 Rust tests, and reproducible sidecar build.
- `npm run build:app` produced the Apple Silicon macOS app bundle at
  `spikes/tauri_realtime/src-tauri/target/release/bundle/macos/Hey Jarvis
  Tauri Realtime Spike.app`.
- A no-microphone/no-network GUI startup check loaded `tauri://localhost`,
  showed `ready · add OPENAI_API_KEY to spike .env`, and kept the live-start
  control disabled.
- The rebuilt app exited with no residual sidecar process.
- Final root `./init.sh` passed 380 project tests, dry/fake pipeline smoke, and
  Realtime fake smoke, demonstrating that the root product remains unaffected.

## Live gate

No microphone permission, real device capture, OpenAI request, or billable
Realtime session was used for this coding record. The next step requires the
user to place a key in the ignored spike-local `.env` and explicitly authorize
the built-in-microphone/speaker trial.

The later authorized live run exposed two cleanup gaps that were corrected
inside the spike: parent-loss self-termination and a callback-based, two-second
bounded microphone reacquisition probe after a 300 ms WebKit release window.
Those live corrections are documented in `F086-live-attempt-1.md` and
`F086-live-attempt-2.md`; this coding record still does not claim evaluator
approval.

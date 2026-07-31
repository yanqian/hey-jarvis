# F088 Fast Coding Evidence

FAST_CODING_EVIDENCE: F088
CODING_PASS: F088

## Result

The accepted wake, Realtime, tool, language, semantic-ending, privacy, and
cleanup runtime is integrated behind the production Tauri sidecar protocol and
WKWebView media boundary. Offline verification and the explicitly authorized
Apple Silicon live acceptance pass. F088 remains `in_progress`; this coding
record does not claim `EVAL_PASS`.

## Implementation

- Added a product sidecar entrypoint that composes the existing wake detector,
  Realtime controller/coordinator, acknowledgement player, six-tool provider
  router, validated settings, and privacy behavior without importing spike
  code or launching Chrome.
- Advanced the strict native/sidecar protocol to version 2 with explicit
  Application Support and bundle-resource paths plus an optional product
  loopback control URL.
- Added an unguessable per-launch loopback capability exchange that becomes an
  HttpOnly, SameSite cookie; unauthenticated loopback requests fail closed.
- Reused the accepted browser media surface inside WKWebView for microphone
  capture, disabled-track readiness, unified WebRTC, remote audio,
  interruption, tool results, and complete media teardown. The API key never
  enters JavaScript or the protocol.
- Added a macOS microphone usage description and bundled acknowledgement asset.
- Made source-Python launch debug-only. Release launch selects only the
  bundle-resource `sidecar/hey-jarvis-sidecar` executable and fails closed;
  F090 owns producing that executable and complete runtime bundle.
- Preserved the independent CLI and removed product reliance on cwd, root
  `.env`, Chrome, terminal PATH, or separately installed release Python.
- Extended real-runtime startup to a bounded 30 seconds, surfaced redacted
  startup error codes, and explicitly focused the native window.

## Verification

- `./init.sh` passed with 388 project tests, 7 sidecar tests, 6 Rust tests,
  frontend syntax, CLI dry/fake smokes, and the Realtime fake smoke.
- The Realtime fake smoke proved two turns, deliberate barge-in, calculator,
  weather, local-time, FX, stock, semantic ending, cleanup, and wake recovery.
- Focused product tests cover source/spike isolation, WKWebView ownership,
  secret exclusion, explicit paths, release executable selection, microphone
  usage text, loopback capability bootstrap, and startup error redaction.
- `npm run build` produced the release native binary; an unsigned local Debug
  `.app` was also built for the authorized device trial.
- `git diff --check` passed.
- Live acceptance is recorded in `F088-live-acceptance.md` with one discovered
  external Chrome-host conflict isolated and removed before the clean pass.

## Boundaries

F088 does not implement Keychain/first-run configuration (F089), construct the
packaged Python/model executable (F090), add durable diagnostics and crash
recovery (F091), sign/notarize a DMG (F092), or publish the beta/portfolio
surface (F093). No automatic evaluator evidence is written here.

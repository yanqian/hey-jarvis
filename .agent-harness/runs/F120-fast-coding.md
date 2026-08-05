# F120 fast coding evidence

FAST_CODING_EVIDENCE: F120

CODING_PASS: F120

## Implementation

- The sidecar reads the bounded `en` or `zh-CN` preference exactly once in
  `begin_handoff`; missing, malformed, oversized, or unsupported values default
  safely to English. The resulting `cue_locale` is attached to the start
  command and cleared only when that handoff finishes.
- The product runtime validates both English canonical cues together with the
  existing Mandarin cues before binding the loopback host. Tauri packages all
  four WAV/manifest pairs with their canonical digests.
- Realtime settings publish locale-explicit metadata and URLs for all four
  cues. The browser rejects an incomplete locale set and preloads all four
  before reporting `armed`.
- Cached ACK playback selects `command.cue_locale`; cached farewell playback
  selects the retained `activeCueLocale`. UI language polling never controls
  either selection, so changing Settings during a session affects the next
  wake only.
- Both cue types continue through the shared browser audio element at the
  configured gain. ACK completion remains one of the existing input-readiness
  barriers. Cached farewell sends no model `response.create`, keeps input
  muted, and retains the existing exactly-once stop and wake-recovery path.
- Ordinary Realtime session instructions and per-turn language behavior were
  not changed.

## Verification

- Focused language-cue, English-asset, cached-ACK, Realtime-host, sidecar, and
  packaging suite: 80 tests passed using `.venv/bin/python`.
- Complete project suite: 470 tests passed using `.venv/bin/python`.
- Mac sidecar suite: 12 tests passed using `.venv/bin/python`.
- Rust suite: 30 tests passed.
- `node --check src/realtime_host/static/app.js`: passed.
- `.venv/bin/python -m src.realtime.fake_smoke`: passed, including two turns,
  interruption, exact end phrase, closure, and wake recovery.
- `npm run tauri -- build --debug --bundles app`: passed. The refreshed bundle
  contains all four locale-explicit WAV/manifest pairs; English WAV bundle
  digests match their canonical files.
- Final `./init.sh`, with the project `.venv` first on `PATH`: passed with 470
  project tests, 12 Mac frontend/sidecar tests, 30 Rust tests, dry-run,
  fake-backend smoke, and Realtime fake smoke.
- `git diff --check`: passed.

## Safety and privacy

- No paid generation or dependency installation occurred during F120.
- Tests and durable evidence retain no audio, transcript, answer, credential,
  SDP, ICE, or provider payload.
- Candidate directories and unrelated existing `tmp/` logs remain ignored and
  unmodified.

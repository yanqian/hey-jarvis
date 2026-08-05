# F119 fast coding evidence

FAST_CODING_EVIDENCE: F119

CODING_PASS: F119

## Authorization and bounded paid generation

- The owner explicitly authorized at most three `alloy` candidates for the
  English ACK `I'm here. Yes?` and at most three for the English farewell
  `See you.`.
- Exactly six successful `gpt-4o-mini-tts` calls were made: ACK styles light,
  warm, and crisp; farewell styles light, warm, and casual. No retry or seventh
  call occurred.
- The first attempted command used the system interpreter and stopped before
  SDK import or network activity. The existing ignored `.venv` already held
  the required SDK; no dependency was installed or upgraded.
- Candidate audio and privacy-safe manifests remain under the Git-ignored
  `tmp/realtime-english-cue-candidates/`; provider bodies, credentials,
  session identifiers, request identifiers, and unrelated audio were not
  retained.

## Owner selection

- The owner auditioned all six candidates on the target Mac and explicitly
  selected `candidate-02` from both groups.
- Selected ACK: warm, 1,416 ms, SHA-256
  `ad30695e0777bfb61d9dc4b4ddb7ca2fb81a11c3197ce34455eb375de995d7dc`.
- Selected farewell: warm, 738 ms, SHA-256
  `1432db3c588f772d5572dce3d6581adf4b2e5d900235b93c7670ac3260303e6f`.

## Implementation and verification

- Added one bounded generator/promotion/preparation path for locale-explicit
  English cues. Paid generation rejects missing owner authorization and labels
  beyond `candidate-03`.
- Candidate and selected-asset validation enforces exact phrase metadata,
  `en`, `alloy`, playback gain 0.5, 24 kHz mono 16-bit PCM WAV, cue-specific
  duration bounds, at most 80 ms leading/trailing silence, exact manifest
  fields, and SHA-256 integrity.
- Promotion requires explicit owner confirmation. Preparation copies both WAV
  and manifest byte-for-byte and rejects missing, corrupt, tampered,
  wrong-phrase, wrong-rate, or unselected assets.
- Tauri resources and product-sidecar resource constants package the two
  English assets beside the unchanged Mandarin ACK and farewell.
- `python3 -m unittest tests.test_english_voice_cues
  tests.test_macos_sidecar_packaging app.sidecar.tests.test_product_sidecar`:
  18 passed.
- Selected prepare command: pass with matching ACK and farewell digests.
- `npm run tauri -- build --debug`: pass.
- Final `./init.sh`: pass with 465 project tests, 11 Mac
  frontend/fake-sidecar tests, 30 Rust tests, dry-run, fake-backend smoke, and
  Realtime fake smoke.
- `git diff --check`: pass; the four accepted Mandarin asset files are
  byte-unchanged from `HEAD`.

## Safety

- No microphone capture, ordinary conversation, diagnostic mutation, or
  runtime cue selection was performed. F120 owns language-based playback.
- The accepted Mandarin asset files and manifests were not modified.

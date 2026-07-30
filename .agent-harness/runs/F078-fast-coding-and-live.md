# F078 Fast Coding and Live Evidence

Feature: F078 - Make the short acknowledgement reproducible

Date: 2026-07-28
Result: Coding complete; exact accepted cue recovered and verified

## Human candidate history

- The first 3.0-speed 384 ms `嗯` was rejected as too fast and unclear.
- A 984 ms candidate was rejected as unclear and too quiet.
- A 360 ms candidate measured near silence and was inaudible.
- Later 720–1,032 ms candidates were rejected as muffled and ineffective as
  alerts.
- None of those rejected candidates was installed.
- The existing 480 ms runtime cue remained the only clear, audible cue accepted
  by the user. F080's successful live session used those exact bytes before
  normal post-cue questions, barge-in, semantic ending, and wake recovery.

## Corrected implementation

- Promoted the exact accepted 480 ms bytes to the checked-in canonical asset
  `assets/wake_acknowledgement_alloy.mp3`.
- `--prepare-acknowledgement` no longer calls TTS or needs an OpenAI key or
  network. It verifies the canonical SHA-256, copies to a same-directory
  temporary file, verifies the copy, checks the `afinfo` duration ceiling, and
  atomically installs the runtime asset.
- Missing, changed, excessive, copy, inspection, or atomic-install failures
  preserve the prior asset and return content-redacted diagnostics.
- Runtime diagnostics apply the same exact accepted digest and duration
  boundaries. Exact digest matching is stricter than a decoded near-silence
  threshold: no changed, quiet, silent, or muffled replacement can install.

## Target-Mac evidence

- Preparation succeeded with `OPENAI_API_KEY` empty.
- Canonical SHA-256:
  `7a2729046e2b0acdbec345d3d825768ac0e30f9228994092382a885f82109b0c`.
- Runtime SHA-256 matches the canonical digest exactly.
- `afinfo` reports 0.480000 seconds.
- The user had already accepted these exact bytes as the clear, audible local
  `嗯`; the rejected later candidates did not replace them.
- F080 live evidence covers the same runtime bytes and confirms a normal
  post-cue Realtime conversation on the target Mac.

## Verification

- Focused config, preparation, player, diagnostic, documentation, and OpenAI
  tests passed.
- Copy and atomic-install failure preservation are covered explicitly.
- Final `./init.sh` passed: harness verification, 373 project tests, dry-run,
  pipeline fake smoke, and Realtime fake smoke.
- `git diff --check` passed.

FAST_CODING_EVIDENCE: F078
CODING_PASS: F078

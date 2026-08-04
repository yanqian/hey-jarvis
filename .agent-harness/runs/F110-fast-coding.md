# F110 fast coding evidence

## Scope

- Added a one-shot, owner-authorized workflow that digitally captures only the
  correlated remote Realtime acknowledgement stream.
- Validated the fixed Mandarin phrase, mono PCM WAV format, bounded duration
  and size, model/voice identifiers, output gain, and SHA-256 before retaining
  each candidate.
- Kept candidates under the Git-ignored `tmp/realtime-ack-candidates/` path and
  required explicit owner confirmation before promotion.
- Added deterministic capture cleanup, state correlation, privacy-safe
  manifests, canonical-asset promotion, and offline runtime preparation.

## Verification

- Focused ACK asset, host, coordinator, Mac shell, and Realtime acknowledgement
  tests: passed.
- JavaScript syntax, Realtime fake smoke, `git diff --check`: passed.
- Final `./init.sh`: passed with 445 project tests, 10 Mac frontend/fake-sidecar
  tests, 25 Rust tests, dry-run, pipeline fake smoke, and Realtime fake smoke.

## Owner-authorized live evidence

- The owner explicitly authorized up to three paid short Realtime sessions and
  deliberate retention of the fixed ACK candidates.
- Three digitally captured candidates passed phrase, format, gain, duration,
  digest, input-readiness, teardown, and wake-recovery checks. Their durations
  were 3,352 ms, 2,429 ms, and 2,913 ms.
- The owner selected `candidate-02`. Its `gpt-realtime-2.1` / `alloy` / 0.5-gain
  48 kHz mono PCM asset was promoted with duration 2,429 ms and SHA-256
  `c4bc743a401f95bcbaef7206493bf89f304ed4610690481d277c489d6342ac88`.
- Offline preparation reproduced the same digest at `var/realtime-ack.wav`
  without a network request. Unselected candidates remain untracked and were
  not deleted.
- No microphone recording, ordinary answer, farewell, session identifier,
  credential, SDP, ICE, or provider payload entered durable evidence.

FAST_CODING_EVIDENCE: F110
CODING_PASS: F110

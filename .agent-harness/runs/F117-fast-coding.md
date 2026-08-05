# F117 fast coding evidence

FAST_CODING_EVIDENCE: F117
CODING_PASS: F117

- Owner selected candidate-03 after rejecting candidate-01 and comparing two
  softer alternatives.
- Canonical asset: `assets/realtime_farewell_alloy_zh.wav`, 580 ms, 24 kHz,
  mono 16-bit PCM, `alloy`, gain 0.5. The owner approved removing 20 ms from
  the front after silence analysis; the natural trailing decay is unchanged.
- SHA-256: `cc2c36a568cb1d339cd1eec203f70b0a7f0351761e1553a18820463c617728d8`.
- Default `REALTIME_FAREWELL_MODE=cached` prevalidates and preloads the asset.
- Cached close mutes input, sends no farewell `response.create`, plays through
  the shared browser audio element, and waits for playback completion before
  the existing bounded teardown and wake recovery.
- `REALTIME_FAREWELL_MODE=realtime` retains the F107 generated rollback.
- Verification: 71 focused tests; 458 full project tests; 11 packaged sidecar
  tests; 27 Rust tests; JavaScript syntax; Realtime fake smoke; asset digest and
  manifest validation.
- Owner audition proves candidate selection. The integrated target-Mac
  wake/conversation/farewell/wake flow also passes; the owner heard the cached
  farewell, judged its ending natural, and successfully woke the assistant a
  second time. Privacy-bounded evidence is in `F117-live-acceptance.md`.
- No candidate other than the selected canonical asset is packaged or tracked.
  No conversation audio, transcript, credential, SDP, ICE, or provider payload
  is retained.

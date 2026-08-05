# F117 Mandarin farewell candidate generation

FAST_CODING_EVIDENCE_PENDING: F117

- Owner authorization: explicit request to generate the Mandarin cached farewell.
- Sent externally: fixed text `再见` and a fixed Mandarin delivery instruction only.
- Generator: `gpt-4o-mini-tts`, voice `alloy`, WAV output.
- Retained candidate: `tmp/realtime-farewell-candidates/candidate-01.wav`.
- Validated result: 827 ms, 24 kHz, mono 16-bit PCM, gain metadata 0.5.
- SHA-256: `2fc993a1eb99c2564c418ba5b2f8c3ac3c7afb8f04ffb7ae7760adac386e95a6`.
- Three earlier paid generation responses were rejected and discarded while
  diagnosing the provider's streaming RIFF length sentinel; the fourth request
  passed after canonical header finalization. No conversation audio, transcript,
  credential, SDP, ICE, or provider payload was retained.
- Owner audition and explicit promotion are still required. Production remains
  on the existing Realtime-generated farewell meanwhile.

## Owner feedback and follow-up candidates

- Candidate-01 verdict: rejected as too heavy and clenched-sounding.
- Candidate-02: `mandarin-farewell-soft-v1`, 784 ms, SHA-256
  `e1102fa8c1c850a0ff0a992d1f2eb7ea01b009b892b9e3ee1e5b536042175e46`.
- Candidate-03: `mandarin-farewell-light-v1`, originally 600 ms, SHA-256
  `292d911d87a7807552a40ee618708e1fbf16fa1a893c43854399c9c48f738135`.
- Each follow-up sent only fixed text `再见` plus its non-private delivery
  instruction and incurred one short paid TTS request.
- Owner selected Candidate-03. Before promotion, silence analysis showed speech
  onset at about 40 ms and a natural trailing decay rather than surplus ending
  silence. With explicit owner approval, 20 ms was removed from the front only;
  the tail was preserved to avoid an abrupt cutoff.
- Promoted canonical asset: 580 ms (13,924 frames at 24 kHz), SHA-256
  `cc2c36a568cb1d339cd1eec203f70b0a7f0351761e1553a18820463c617728d8`.

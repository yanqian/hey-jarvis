# F060 Fast Coding Evidence

FAST_CODING_EVIDENCE: F060

CODING_PASS: F060

## Summary

Implemented diagnosis-only observability for the F059 RT003 natural-speech
failure. The browser now derives bounded 500 ms normalized RMS/peak summaries
from the exact microphone `MediaStream` sent over WebRTC and labels whether
remote playback is active. The coordinator strictly validates and rounds those
events. A guided live command compares silence, one utterance without playback,
and one utterance during the deterministic counting answer, then returns an
evidence-backed diagnostic category without changing Realtime tuning or
relabelling RT003.

## Verification

- `.venv/bin/python -m unittest tests.test_realtime_host
  tests.test_realtime_input_diagnosis tests.test_realtime_spec_eval
  tests.test_documentation` initially passed 40 tests and passes 41 tests after
  the live-discovered startup-error regression was added.
- Final `./init.sh` passed harness checks, 291 project tests, dry-run,
  fake-backend, and Realtime fake smoke.
- `git diff --check` passed.
- Tests cover exact-stream browser analysis, bounded cadence and teardown
  source assertions, strict coordinator validation, privacy sanitization,
  all five classifier outcomes, guided success/failure cleanup, offline CLI,
  F059 regression, and documentation boundaries.

## Safety and Evidence Boundary

- No Realtime VAD threshold, output volume, media constraint, echo-processing
  setting, RT003 timing oracle, or tracked private fixture was changed.
- Persisted diagnosis evidence contains only allowlisted lifecycle metadata and
  bounded normalized summaries; it excludes audio, sample arrays, transcripts,
  utterance text, credentials, and tool payloads.
- A live F060 run still requires explicit authorization for its distinct
  two-utterance microphone/OpenAI/cost boundary. Until that run exists, F060
  remains in progress and no root-cause category is claimed.

## Evaluator Result

Pending a separate cold-start Evaluator Agent after authorized live evidence is
recorded. This coding record intentionally contains no evaluator verdict and
does not mark F060 done.

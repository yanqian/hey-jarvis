# F057 fast coding evidence

FAST_CODING_EVIDENCE: F057
CODING_PASS: F057

## Implemented

- Reconciled README, deployment, manual testing, environment defaults, CLI help, and selected-backend diagnostics for arming lifetime, pipeline default, Realtime opt-in, model/voice/output gain, API cost, pre-wake privacy, exits, calculator-only scope, bounded redacted diagnostics, troubleshooting, and packaging deferral.
- Expanded the dependency-free Realtime smoke to cover wake, exclusive handoff, connection, two turns, assistant completions, interruption, calculator output, end phrase, close, and restored WAIT_WAKE without hardware, network, credentials, or wall-clock sleep.
- Prevented command/tool content from entering default coordinator evidence, globally redacted unsafe evidence strings, and retained the 200-event bound.
- Added validated quiet-speakerphone controls after real built-in-speaker testing reproduced intermittent self-echo across output-only tuning: direct browser playback gain `0.1` plus documented server-VAD threshold `0.8` passed five consecutive full cycles while preserving 15-118 ms deliberate interruption.
- Expanded private acoustic replay to cover wake, two response-bound turns, calculator tool-call plus spoken continuation, deliberate long-answer barge-in plus continuation, end phrase, and wake recovery. It rejects any unexplained speech start and does not commit audio or transcript text.
- Recorded transcript-free five-cycle real-device evidence separately in `F057-real-device-acceptance.md`.

## Verification

- Focused Realtime fixture/config/host tests pass, including response ownership,
  calculator continuation ordering, VAD threshold bounds, report redaction, and
  rejection of unexplained speech starts.
- Full discovery passes with 266 tests.
- Pipeline dry-run and fake-backend smoke pass.
- The dependency-free Realtime fake smoke passes the complete MVP lifecycle.
- Selected Realtime diagnostics report output gain `0.1`, server-VAD threshold
  `0.8`, configured credential, loopback-only hosting, and exclusive handoff.
- Final `./init.sh` and `git diff --check` pass.

This is Coding Agent evidence only. It does not contain evaluator approval, write `EVAL_PASS`, or mark F057 done.

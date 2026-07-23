# F061 Fast Coding Evidence

FAST_CODING_EVIDENCE: F061

CODING_PASS: F061

## Summary

RT003 version 2 now separates operator coordination from its one real speech
action. The live runner waits for explicit readiness before playing the private
wake fixture or acquiring a timeout-bound Realtime session. It then establishes
the session, promptly posts the long-answer request, observes the exact
active-session `host_response_created` event, and immediately observes the
single near-end interruption utterance. The prepared operator speaks only once
counting is audible, so that one in-band utterance is both audible confirmation
and barge-in evidence.

## Verification

- `python3 -m unittest tests.test_realtime_spec_eval
  tests.test_documentation` passed 22 tests.
- Final `./init.sh` passed harness verification, 295 project tests, dry-run,
  fake-backend smoke, and Realtime fake smoke.
- Deterministic fakes prove that wake/session acquisition and the long-answer
  request cannot precede readiness, and that speech observation cannot precede
  the exact long-answer marker.
- Regressions cover operator cancellation, closed input, an answer ending
  before audible confirmation, early host closure, timeout, sanitized failure
  evidence, and bounded cleanup.
- The first authorized live attempt exposed that a readiness gate placed after
  session establishment could outlive the existing idle timeout. The coding
  retry moved that gate before wake playback; focused verification still passes
  22 tests. The honest failure is recorded in `F061-live-attempts.md`.
- The second attempt proved that a separate audible-confirmation round trip can
  outlive the answer itself. The single real utterance now doubles as in-band
  audible confirmation, and natural completion fails immediately. This avoids
  a longer costlier prompt while preserving every RT003 oracle.

## Preserved Contract

- RT003 still requires exactly one `live_near_end` human speech action.
- The cancelled old response, 1000 ms cancellation bound, completed
  continuation, restored wake ownership, and privacy allowlist are unchanged.
- No Realtime model, voice, VAD threshold, output volume, capture constraint,
  echo-processing setting, product interruption logic, private fixture, or
  historical F059/F060 verdict was changed.

## Live Acceptance

The explicitly authorized built-in-microphone/speaker RT003 version-2 retry
passed with one active-session near-end `host_speech_started`, old-response
`cancelled` after 69 ms, completed continuation, and restored wake ownership.
The sanitized record is summarized in `F061-live-attempts.md`.

After live acceptance, final `./init.sh` again passed harness verification, all
295 project tests, dry-run, fake-backend smoke, and Realtime fake smoke. F061
remains in progress until a separate cold-start Evaluator Agent accepts the
feature. This coding record intentionally contains no evaluator verdict.

## Evaluator Retry

The first cold-start evaluator rejected one stale README sentence that still
claimed two fail-closed gates. The README now states the implemented one
pre-session readiness gate plus in-band confirmation workflow. A documentation
regression requires that wording, requires the absence of a second
terminal/chat round trip in README and manual guidance, and rejects the stale
two-gate phrase.

The retry-focused suite passes 23 tests. Final recovery verification passes
harness checks, 296 project tests, dry-run, fake-backend smoke, and Realtime
fake smoke.

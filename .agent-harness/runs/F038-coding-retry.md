# Run Record: F038 - coding retry after evaluator failure

## Evaluator feedback

The first evaluation found that `ACK_GUARD_MIN_QUIET_SECONDS=0` was accepted and caused the boundary loop to consider a loud first chunk quiet-observed without any noise seed.

## Retry

- Configuration now rejects non-positive quiet duration whenever ACK guard is enabled.
- Runtime boundary handling independently fails closed when quiet duration or maximum suppression is non-positive.
- Focused config and state-machine regressions cover both validation and defensive runtime behavior.
- Focused retry suite passed with 53 tests; final `./init.sh` passed with 174 project tests plus dry-run and fake-backend smoke.
- Failure domain: implementation_gap
- Harness improvement: none required in product code; the independent evaluator found a validation edge case and the retry adds durable regression coverage. The suggested general harness checklist improvement remains recorded in the evaluator failure artifact.

FAST_CODING_EVIDENCE: F038
CODING_PASS: F038

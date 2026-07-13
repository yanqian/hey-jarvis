# F044 Evaluation

Date: 2026-07-13

Cold-start evaluation reconstructed repository context from `AGENTS.md`, `.agent-harness/feature_list.json`, `.agent-harness/progress.md`, recent git history, and `./init.sh`, then inspected the `F044` implementation, tests, README update, fast-work handoff, and fast coding evidence.

Implementation verification passed: `./init.sh` passed, `.venv/bin/python -m unittest tests.test_tools tests.test_state_machine` passed, and `.venv/bin/python -m src.main --text '一加一等于几'` plus `.venv/bin/python -m src.main --text '一加一等於幾'` both routed to `calculator` with `expression:1+1` and `The answer is 2.`. Conservative ambiguity handling also worked for `.venv/bin/python -m src.main --text '一二三加四是多少'`, which correctly fell through to chat instead of guessing.

The feature cannot be accepted because planning did not add the required normalized SPEC entry for `F044`. Searches of `SPEC.md` and `.agent-harness/SPEC.md` found no `F044` requirement block and no normalized fields for this feature's goal, included scope, excluded scope, core flows, constraints, ambiguities or assumptions, required capabilities, implementation paths, and verification surface. Under `docs/spec-normalization.md`, `docs/agent-workflow.md`, and `QUALITY.md`, that is a `requirement_gap` and blocks acceptance even when code and tests pass.

## Failure Analysis

- Failure domain: requirement_gap
- Failure summary: `F044` was appended and implemented without a durable normalized SPEC addition describing the feature's goal, scope, flows, constraints, assumptions, capabilities, implementation paths, and verification surface.
- Harness improvement: No harness change required; the current rules already reject this condition. `F044` must be normalized in `SPEC.md` before evaluator approval can pass.
- Follow-up feature: none

EVAL_FAIL: F044: requirement_gap: missing normalized SPEC entry for F044 in SPEC.md/.agent-harness/SPEC.md with required goal, included scope, excluded scope, core flows, constraints, ambiguities or assumptions, required capabilities, implementation paths, and verification surface; harness improvement assessment: existing normalization rules are sufficient, feature must be normalized before acceptance.

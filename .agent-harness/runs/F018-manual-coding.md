# Run Record: F018 - Gate post-playback wake on observed quiet

## Summary

- Date: 2026-07-05
- Agent role: Coding Agent manual fallback
- Feature: F018 - Gate post-playback wake on observed quiet
- Result: Implemented

## Repository State

- Starting commit: d700c61 F016 Fix empty transcription recovery
- Ending commit: uncommitted working tree
- Working tree status: includes F017/F018 implementation, docs, harness state, and pre-existing local manual-test artifacts under `tmp/`, `debug/`, and `.DS_Store`

## Commands Run

```bash
./init.sh
make work
python3 -m unittest tests.test_state_machine tests.test_config tests.test_documentation tests.test_main
python3 -m json.tool .agent-harness/feature_list.json
./init.sh
```

## Evidence

- Tests: focused config, state-machine, documentation, and main tests passed, 29 tests.
- Recovery: final `./init.sh` passed with 18 validated features, 67 project tests, dry-run smoke, and fake-backend smoke.
- Logs: fake-backend smoke now shows fixed post-playback drain, a quiet gate waiting for 0.50s, 7 quiet-gate chunks consumed, and `WAIT_WAKE` ready only after `quiet=0.56s`.
- External behavior verification: no live microphone, speaker, or OpenAI calls were automated; tests simulate wake-positive residual chunks after cooldown followed by quiet chunks.
- Capability gaps: root `make work` is unavailable in this hidden-layout project, so work used documented manual fallback.

## Failure Analysis

- Failure domain: none
- Failure summary: F017's fixed cooldown did not stop the user-observed post-playback false wake; residual wake-positive frames still occurred immediately after the cooldown.
- Harness improvement: no harness change required; this is a product behavior follow-up feature.
- Follow-up feature: none

## Files Changed

- `.agent-harness/SPEC.md`
- `.agent-harness/feature_list.json`
- `.agent-harness/progress.md`
- `.agent-harness/runs/F018-manual-coding.md`
- `.agent-harness/runs/F018-evaluation.md`
- `.env.example`
- `README.md`
- `DEPLOYMENT.md`
- `MANUAL_TESTING.md`
- `src/config.py`
- `src/main.py`
- `src/state_machine.py`
- `tests/test_config.py`
- `tests/test_state_machine.py`

## Evaluator Result

```text
Not evaluated in this Coding Agent run.
```

## Follow-Up

- Manually retest M022 by completing playback and saying nothing afterward. Expected behavior: quiet-gate logs appear and the assistant remains in `WAIT_WAKE`.

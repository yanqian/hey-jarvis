# Run Record: F018 - Gate post-playback wake on observed quiet

## Summary

- Date: 2026-07-05
- Agent role: Evaluator Agent manual review
- Feature: F018 - Gate post-playback wake on observed quiet
- Result: Passed

## Repository State

- Starting commit: d700c61 F016 Fix empty transcription recovery
- Ending commit: uncommitted working tree
- Working tree status: includes F017/F018 implementation and prior untracked local manual-test artifacts

## Commands Run

```bash
python3 -m unittest tests.test_state_machine tests.test_config tests.test_documentation tests.test_main
python3 -m json.tool .agent-harness/feature_list.json
./init.sh
```

## Evidence

- Acceptance 1: `src/state_machine.py` performs fixed cooldown, then waits for `POST_PLAYBACK_QUIET_SECONDS` of quiet audio before logging ready.
- Acceptance 2: suppressed post-playback audio advances the detector via `score` or `detect`, but detections are discarded; wake-positive suppressed scores reset quiet accumulation.
- Acceptance 3: `src/config.py`, `.env.example`, README, DEPLOYMENT, and MANUAL_TESTING document and validate quiet seconds, quiet RMS, and max suppression settings.
- Acceptance 4: focused state-machine tests simulate residual wake-positive chunks after cooldown and prove the loop returns to `WAIT_WAKE` without a second `RECORDING`.
- Acceptance 5: progress and run records document the second observed failure and manual M022 retest path.
- Final recovery: `./init.sh` passed with 67 project tests plus dry-run and fake-backend smoke.

## Failure Analysis

- Failure domain: none
- Failure summary: none
- Harness improvement: none required
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
EVAL_PASS: F018
```

## Follow-Up

- Run live M022 with real playback and no speech after playback.

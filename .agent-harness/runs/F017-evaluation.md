# Run Record: F017 - Suppress post-playback false wake detection

## Summary

- Date: 2026-07-05
- Agent role: Evaluator Agent manual review
- Feature: F017 - Suppress post-playback false wake detection
- Result: Passed

## Repository State

- Starting commit: d700c61 F016 Fix empty transcription recovery
- Ending commit: uncommitted working tree
- Working tree status: includes F017 implementation and prior untracked local manual-test artifacts

## Commands Run

```bash
python3 -m unittest tests.test_config tests.test_state_machine tests.test_documentation tests.test_main
python3 -m json.tool .agent-harness/feature_list.json
./init.sh
```

## Evidence

- Acceptance 1: `src/state_machine.py` drains the configured post-playback cooldown window without calling wake detection, and tests assert playback residue is not sent to the detector.
- Acceptance 2: wake detection now requires `WAKE_CONFIRMATION_FRAMES` consecutive positives and ignores overflowed chunks; tests cover single-candidate reset and overflow skip.
- Acceptance 3: `src/config.py`, `.env.example`, README, DEPLOYMENT, and MANUAL_TESTING document the default cooldown and confirmation settings; fake-backend smoke remains deterministic.
- Acceptance 4: focused tests simulate playback residue and overflowed chunks without real hardware.
- Acceptance 5: progress and run records document the observed failure and manual retest path.
- Final recovery: `./init.sh` passed with 66 project tests plus dry-run and fake-backend smoke.

## Failure Analysis

- Failure domain: none
- Failure summary: none
- Harness improvement: none required
- Follow-up feature: none

## Files Changed

- `.agent-harness/SPEC.md`
- `.agent-harness/feature_list.json`
- `.agent-harness/progress.md`
- `.agent-harness/runs/F017-manual-coding.md`
- `.agent-harness/runs/F017-evaluation.md`
- `.env.example`
- `README.md`
- `DEPLOYMENT.md`
- `MANUAL_TESTING.md`
- `src/config.py`
- `src/state_machine.py`
- `tests/test_config.py`
- `tests/test_state_machine.py`

## Evaluator Result

```text
EVAL_PASS: F017
```

## Follow-Up

- Run the live M022 manual test in `MANUAL_TESTING.md` with real playback and no speech after playback.

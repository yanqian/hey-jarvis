# Run Record: F017 - Suppress post-playback false wake detection

## Summary

- Date: 2026-07-05
- Agent role: Coding Agent manual fallback
- Feature: F017 - Suppress post-playback false wake detection
- Result: Implemented

## Repository State

- Starting commit: d700c61 F016 Fix empty transcription recovery
- Ending commit: uncommitted working tree
- Working tree status: includes F017 source, tests, docs, harness state, and pre-existing manual-test artifacts under `tmp/`, `debug/`, and `.DS_Store`

## Commands Run

```bash
./init.sh
make work
python3 -m unittest tests.test_config tests.test_state_machine tests.test_documentation tests.test_main
python3 -m json.tool .agent-harness/feature_list.json
./init.sh
```

## Evidence

- Tests: focused unit/documentation tests passed, 28 tests.
- Recovery: final `./init.sh` passed with 17 validated features, 66 project tests, dry-run smoke, and fake-backend smoke.
- Logs: fake-backend smoke now shows `wake word candidate 1/2`, post-playback suppression for `1.00s`, and 13 discarded microphone chunks before `WAIT_WAKE` is ready.
- External behavior verification: no live microphone, speaker, or OpenAI calls were used; tests simulate playback residue and overflowed chunks.
- Capability gaps: root `make work` is unavailable in this hidden-layout project, so work used documented manual fallback.

## Failure Analysis

- Failure domain: none
- Failure summary: user-observed real runtime false wake immediately after playback, with microphone overflow and empty transcription recovery.
- Harness improvement: no harness change required; the unavailable root `make work` behavior is already recorded as the reason for manual fallback.
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
Not evaluated in this Coding Agent run.
```

## Follow-Up

- Manually retest M022 by completing playback and saying nothing afterward. Expected behavior: post-playback suppression logs appear and the assistant remains in `WAIT_WAKE`.

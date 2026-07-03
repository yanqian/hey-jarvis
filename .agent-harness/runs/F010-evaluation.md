# Run Record: F010 - evaluation

## Summary

- Date: 2026-07-03
- Agent role: Evaluator Agent
- Feature: F010 - Add wake-word debug probes
- Result: Passed

## Repository State

- Starting commit: `309e024 F009 Prevent wake-listening microphone overflow`
- Ending commit: not committed
- Working tree status: F010 implementation, planning state, manual coding evidence, and this evaluator evidence are uncommitted. The selected feature remains `passes=false`, `status="in_progress"` until the harness completion flow records evaluator-gated completion.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_main tests.test_state_machine tests.test_wake_word tests.test_audio_input tests.test_config tests.test_documentation
python3 -m src.main --dry-run
python3 -m src.main --fake-backend
python3 -m src.main --help
.agent-harness/scripts/validate-feature.sh F010
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Evidence

- Tests: root `./init.sh` passed, including harness verification, project compile, full project unittest discovery, dry-run smoke, and fake-backend smoke. Focused F010-related tests passed 30 tests. Full project discovery passed 49 tests. `.agent-harness/scripts/validate-feature.sh F010` passed.
- Logs: live wake debug and `WAKE_DEBUG=1` paths produce `rms`, `peak`, `overflow`, `score`, `threshold`, and `detected` fields. Fake-backend smoke still avoids microphone, OpenAI, and playback while returning to `WAIT_WAKE`.
- Screenshots or traces: none.
- External behavior verification: F010 uses Python standard-library `argparse` and `wave` behavior plus project fake detectors and generated WAV fixtures. Automated verification intentionally avoids physical microphone permission and live openWakeWord execution; those remain documented manual runtime setup requirements.
- Capability gaps: none for automated F010 verification. Real live microphone probing requires local macOS microphone permission and installed wake-word dependencies, which are documented and not bypassed by the automated tests.

## Failure Analysis

- Failure domain: none
- Failure summary: none
- Harness improvement: not required; the feature is normalized in `.agent-harness/SPEC.md`, scoped to one independently verifiable debug capability, implemented in project-owned paths, and manual fallback/evaluator gating were recorded durably.
- Follow-up feature: none

## Files Changed

- `.agent-harness/runs/F010-evaluation.md`

## Evaluator Result

```text
EVAL_PASS: F010
```

## Follow-Up

- Orchestrator or continuation flow may mark F010 done now that evaluator evidence exists.

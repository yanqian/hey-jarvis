# Run Record: F014 - Restore Alexa wake-word runtime

## Summary

- Date: 2026-07-04
- Agent role: Evaluator Agent
- Feature: F014 - Restore Alexa wake-word runtime
- Result: Passed.

## Repository State

- Starting commit: `414fa12 F010-F011 Add wake debug probes`
- Ending commit: not committed
- Working tree status: modified F012/F013/F014 project and harness files remain uncommitted; local audio artifacts and `.DS_Store` are present and were not modified by evaluation.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_wake_word tests.test_config tests.test_main tests.test_audio_input tests.test_documentation tests.test_openai_client tests.test_state_machine
python3 -m unittest discover -s tests -p 'test_*.py'
.agent-harness/scripts/validate-feature.sh F014
```

## Evidence

- Tests: focused F014 suite passed 40 tests covering Alexa loader arguments, ONNX preparation paths, diagnostics, documentation, 1280-sample microphone/debug/replay sizing, wake debug output, and dependent state-machine behavior without real microphone access or live model download.
- Tests: full project test discovery passed 53 tests.
- Recovery: `./init.sh` passed harness verification, project compile, project tests, dry-run smoke, and fake-backend smoke.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F014` passed with F014 still `in_progress` and `passes=false` pending evaluator output/state transition.
- Acceptance: active code uses openWakeWord Alexa constants, ONNX inference framework, Alexa score extraction, 1280-sample frames, explicit `--prepare-wake-word`, diagnostics for missing ONNX assets, README and `.env.example` Alexa setup, and no active Picovoice/PICOVOICE AccessKey requirement.
- Capability gaps: the Porcupine `PICOVOICE_ACCESS_KEY` account requirement is recorded in progress and implementation evidence as the reason for restoring Alexa. F014 removes that missing credential from the active MVP path and restores durable openWakeWord/ONNX setup instead.

## Failure Analysis

- Failure domain: none
- Failure summary: No evaluator failure found.
- Harness improvement: Not required; the feature is normalized in `.agent-harness/SPEC.md`, scoped as one coherent rollback, implemented in project-owned paths, and manual fallback/evaluator gating were recorded durably.
- Follow-up feature: None

## Files Changed

- `.agent-harness/runs/F014-evaluation.md`

## Evaluator Result

```text
EVAL_PASS: F014
```

## Follow-Up

- Orchestrator or a state update may mark F014 done after consuming this evaluator pass.

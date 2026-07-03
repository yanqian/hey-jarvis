# Run Record: F009 - evaluation

## Summary

- Date: 2026-07-03
- Agent role: Evaluator Agent
- Feature: F009 - Prevent wake-listening microphone overflow during model startup
- Result: Passed

## Repository State

- Starting commit: `3afcaf9 F007-F008 Document setup and fix wake-word ONNX setup`
- Ending commit: not committed
- Working tree status: F009 implementation, planning state, manual coding evidence, and this evaluator evidence are uncommitted. The selected feature remains `passes=false`, `status="in_progress"` until the harness completion flow records evaluator-gated completion.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_wake_word tests.test_audio_input tests.test_main tests.test_documentation
python3 -m unittest discover tests
.agent-harness/scripts/validate-feature.sh F009
git diff -- .agent-harness/SPEC.md .agent-harness/feature_list.json .agent-harness/progress.md README.md src/audio_input.py src/main.py src/wake_word.py tests/test_audio_input.py tests/test_documentation.py tests/test_main.py tests/test_wake_word.py .agent-harness/runs/F009-manual-coding.md
```

## Evidence

- Tests: root `./init.sh` passed, including harness verification, project compile, full project unittest discovery, dry-run smoke, and fake-backend smoke. Focused F009 tests passed 15 tests. Full project discovery passed 43 tests. `.agent-harness/scripts/validate-feature.sh F009` passed.
- Logs: `run_assistant_forever()` logs `Preparing Hey Jarvis wake-word detector` and `Hey Jarvis wake-word detector ready` before `open_microphone_stream()` is called. Fake-backend smoke still returns to `WAIT_WAKE`.
- Screenshots or traces: none.
- External behavior verification: no new external CLI, API, credential, or provider behavior is introduced by F009. The real ONNX wake-word capability remains covered by F008; F009 verifies ordering and chunk sizing with deterministic fakes.
- Capability gaps: none for automated F009 verification. Real microphone overflow behavior remains a documented manual runtime condition because automated checks intentionally avoid physical microphone permissions and audio devices.

## Failure Analysis

- Failure domain: none
- Failure summary: none
- Harness improvement: not required; the feature is normalized in `.agent-harness/SPEC.md`, scoped to one independently verifiable runtime bugfix, implemented in project-owned paths, and manual fallback/evaluator gating were recorded durably.
- Follow-up feature: none

## Files Changed

- `.agent-harness/runs/F009-evaluation.md`

## Evaluator Result

```text
EVAL_PASS: F009
```

## Follow-Up

- Orchestrator or continuation flow may mark F009 done now that evaluator evidence exists.

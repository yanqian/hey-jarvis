# Run Record: F015 - Switch Alexa openWakeWord runtime to TFLite

## Summary

- Date: 2026-07-04
- Agent role: Evaluator Agent
- Feature: F015 - Switch Alexa openWakeWord runtime to TFLite
- Result: Passed.

## Repository State

- Starting commit: `ed8404e F012-F014 Restore Alexa wake runtime`
- Ending commit: not committed
- Working tree status: F015 implementation and evidence files are uncommitted; local debug audio artifacts and `.DS_Store` are present and were not modified by evaluation.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_config tests.test_wake_word tests.test_main tests.test_documentation tests.test_debug_oww_file tests.test_state_machine tests.test_openai_client
.agent-harness/scripts/validate-feature.sh F015
rg -n "F015|TFLite|tflite|WAKE_INFERENCE_FRAMEWORK|ai-edge|litert|ONNX|onnx|openWakeWord" README.md .env.example requirements.txt src tests scripts .agent-harness/runs .agent-harness/progress.md .agent-harness/feature_list.json
```

## Evidence

- Tests: `./init.sh` passed harness verification, project compile, 59 project tests, dry-run smoke, and fake-backend smoke.
- Tests: focused F015 suite passed 43 tests covering configuration defaults and validation, macOS ARM64 ONNX guard, detector loader arguments, TFLite and explicit ONNX preparation paths, diagnostics, debug metadata and per-key maximum scores, documentation sync, standalone debug script output, and dependent settings fixtures without real microphone access or live model downloads.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F015` passed with F015 still `in_progress` and `passes=false`, ready for evaluator-gated completion.
- Acceptance: `.agent-harness/SPEC.md` includes normalized F015 goal, included scope, excluded scope, core flows, constraints, ambiguities or assumptions, required capabilities, implementation paths, verification surface, and decomposition rationale.
- Acceptance: active configuration defaults and `.env.example` document `WAKE_BACKEND=openwakeword`, `WAKE_MODEL=alexa`, `WAKE_INFERENCE_FRAMEWORK=tflite`, and `WAKE_THRESHOLD=0.5`; invalid wake backend and inference framework values are rejected.
- Acceptance: `WakeWordDetector` receives configured model, threshold, and inference framework, passes `inference_framework` to `openwakeword.model.Model`, extracts configured model scores with a safe single-key fallback, and defaults to Alexa/TFLite.
- Acceptance: model preparation and diagnostics are framework-aware; TFLite checks `.tflite` assets and LiteRT capability, while ONNX is explicit and non-default.
- Acceptance: live/file wake debug and `scripts/debug_oww_file.py` report requested model, selected inference framework, loaded model keys, and per-key maximum scores.
- Acceptance: macOS ARM64 ONNX selection fails fast with an actionable error telling the user to use TFLite.
- Capability gaps: the TFLite runtime capability is made durable through `requirements.txt`, diagnostics, README setup/troubleshooting, and tests; no required capability was bypassed.

## Failure Analysis

- Failure domain: none
- Failure summary: No evaluator failure found.
- Harness improvement: Not required; the feature is normalized, scoped as one coherent runtime switch, implemented in project-owned paths, and manual fallback/evaluator evidence are recorded durably.
- Follow-up feature: None

## Files Changed

- `.agent-harness/runs/F015-evaluation.md`

## Evaluator Result

```text
EVAL_PASS: F015
```

## Follow-Up

- Mark F015 done only as part of the harness evaluator-gated state transition.

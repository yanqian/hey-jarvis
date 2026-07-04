# Run Record: F012 - Switch wake word to Alexa evaluation

## Summary

- Date: 2026-07-03
- Agent role: Evaluator Agent
- Feature: F012 - Switch wake word to Alexa
- Result: Accepted.

## Repository State

- Starting commit: `414fa12 F010-F011 Add wake debug probes`
- Ending commit: not committed
- Working tree status: modified F012 project and harness state files plus local untracked artifacts; evaluator added this run record only.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_wake_word tests.test_config tests.test_documentation tests.test_main tests.test_state_machine
python3 -m unittest discover -s tests -p 'test_*.py'
.agent-harness/scripts/validate-feature.sh F012
.venv/bin/python - <<'PY'
import openwakeword
print(sorted(openwakeword.MODELS.keys()))
print(openwakeword.MODELS.get("alexa"))
print(openwakeword.FEATURE_MODELS)
PY
.venv/bin/python - <<'PY'
from src.wake_word import required_wake_word_model_paths, OPENWAKEWORD_MODEL_KEY, OPENWAKEWORD_MODEL_NAME
paths = required_wake_word_model_paths()
print("model_name", OPENWAKEWORD_MODEL_NAME)
print("model_key", OPENWAKEWORD_MODEL_KEY)
for name, path in sorted(paths.items()):
    print(name, path.name, path.is_file())
PY
```

## Evidence

- Tests: focused F012-adjacent unittest command passed 30 tests.
- Tests: full project unittest discovery passed 52 tests.
- Recovery: `./init.sh` passed harness verification, project compile, full tests, dry-run smoke, and fake-backend smoke.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F012` passed while leaving F012 incomplete pending evaluator output.
- External behavior verification: installed local `openwakeword` metadata includes the built-in `alexa` key, `alexa_v0.1.tflite` metadata, and feature model metadata. Project code converts those metadata paths and URLs to ONNX assets for preparation and diagnostics.
- Capability gaps: none for automated F012 verification. The local Alexa ONNX file is absent until `python -m src.main --prepare-wake-word` runs with network access, and diagnostics report that setup requirement instead of treating the runtime as ready.

## Failure Analysis

- Failure domain: none
- Failure summary: No evaluation failure.
- Harness improvement: Not required; the feature is normalized, narrowly decomposed, implemented in project-owned paths, and evaluator evidence is now durable.
- Follow-up feature: None

## Files Changed

- `.agent-harness/runs/F012-evaluation.md`

## Evaluator Result

```text
EVAL_PASS: F012
```

## Follow-Up

- Orchestrator or manual state update may mark F012 done using this evaluator evidence.

# F020 Evaluation

EVAL_PASS: F020

Evaluation summary:

- Acceptance 1 satisfied: configuration defaults and `.env.example` use `WAKE_BACKEND=openwakeword`, `WAKE_MODEL=hey_jarvis`, `WAKE_INFERENCE_FRAMEWORK=tflite`, `WAKE_PHRASE=hey jarvis`, and `WAKE_THRESHOLD=0.5`.
- Acceptance 2 satisfied: `WakeWordDetector` defaults to `hey_jarvis`, extracts the configured model key, remains configurable, and preserves the macOS ARM64 ONNX guard.
- Acceptance 3 satisfied: preparation, diagnostics, debug metadata, runtime preload logs, and fake-backend output reflect the configured Hey Jarvis model and phrase.
- Acceptance 4 satisfied: README, DEPLOYMENT, and MANUAL_TESTING document Hey Jarvis setup, debug, and demo flows.
- Acceptance 5 satisfied: focused tests cover defaults, loader arguments, model preparation, debug metadata, documentation, and recovery behavior without live microphone or OpenAI access.

Verification commands:

```text
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m src.main --diagnose
.venv/bin/python -m src.main --wake-file tmp/input.wav
.venv/bin/python -m src.main --fake-backend
```

Follow-up evaluation on AGENTS correction:

```text
.venv/bin/python -m unittest tests.test_config tests.test_wake_word tests.test_main tests.test_documentation tests.test_debug_oww_file
Ran 38 tests
OK

make -C .agent-harness validate FEATURE=F020
feature validation passed: F020

make -C .agent-harness dry-run
No runnable unfinished feature left.
```

The correct hidden-layout orchestrator entrypoint is `make -C .agent-harness work`; AGENTS rules now document that root `make work` is not the orchestrator entrypoint for this repository.

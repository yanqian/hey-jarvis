# F020 Manual Coding Evidence

Feature: F020 - Restore Hey Jarvis TFLite wake word

Manual fallback reason: The user explicitly requested planning and implementation in this interactive session after validating the local `hey_jarvis` TFLite wake-word trial. The work was kept to one selected feature and did not use root `make work`.

Changes implemented:

- Default wake model changed from `alexa` to `hey_jarvis`.
- Default wake phrase changed from `alexa` to `hey jarvis`.
- Wake detector logs now use the configured wake phrase instead of hard-coded Alexa text.
- `.env.example`, README, deployment, and manual testing documentation now describe Hey Jarvis as the accepted wake phrase.
- The low-level openWakeWord debug script now defaults to `hey_jarvis` while still allowing explicit model arguments.
- Focused tests were updated for Hey Jarvis defaults, model preparation paths, debug metadata, documentation coverage, and smoke output expectations.

Verification:

```text
.venv/bin/python -m unittest discover -s tests
Ran 71 tests in 0.079s
OK
```

```text
.venv/bin/python -m src.main --diagnose
[OK] wake_word_models: Required openWakeWord tflite model files are present
```

```text
.venv/bin/python -m src.main --wake-file tmp/input.wav
wake_file metadata model=hey_jarvis framework=tflite loaded_models=hey_jarvis
```

```text
.venv/bin/python -m src.main --fake-backend
State WAIT_WAKE: listening for the hey jarvis wake word
Returned to WAIT_WAKE
```

External behavior evidence: The user reported that the local configured Hey Jarvis TFLite wake-word trial was validated successfully before this feature was planned and implemented.

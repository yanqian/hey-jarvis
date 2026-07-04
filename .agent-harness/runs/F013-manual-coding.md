# Run Record: F013 - Switch wake-word runtime to Porcupine

## Summary

- Date: 2026-07-03
- Agent role: Manual Coding Agent fallback
- Feature: F013 - Switch wake-word runtime to Porcupine
- Result: Implementation completed by manual fallback; awaiting Evaluator Agent review.

## Repository State

- Starting commit: `414fa12 F010-F011 Add wake debug probes`
- Ending commit: not committed
- Working tree status: modified project and harness files, with pre-existing uncommitted F012/F013 state and local audio artifacts preserved.

## Commands Run

```bash
git log --oneline -20
./init.sh
python -m unittest tests.test_wake_word tests.test_config tests.test_main tests.test_audio_input tests.test_documentation
python -m py_compile src/wake_word.py src/config.py src/main.py src/audio_input.py
python3 -m unittest tests.test_wake_word tests.test_config tests.test_main tests.test_audio_input tests.test_documentation
python3 -m py_compile src/wake_word.py src/config.py src/main.py src/audio_input.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q src tests
.agent-harness/scripts/validate-feature.sh F013
./init.sh
python3 -m unittest tests.test_main tests.test_wake_word
python3 -m compileall -q src tests
./init.sh
```

## Evidence

- Tests: focused F013-adjacent `python3 -m unittest tests.test_wake_word tests.test_config tests.test_main tests.test_audio_input tests.test_documentation` passed 33 tests covering Porcupine loader arguments, PCM conversion, frame-size validation, detector cleanup, config and diagnostics, CLI/debug behavior, documentation, and recovery-facing stream defaults without real microphone access or a Picovoice AccessKey.
- Tests: full project unittest discovery passed 54 tests without requiring physical microphone access, OpenAI credentials, Picovoice credentials, live Porcupine execution, or speaker playback.
- Compile: `python3 -m py_compile src/wake_word.py src/config.py src/main.py src/audio_input.py` and `python3 -m compileall -q src tests` passed.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F013` passed while correctly leaving `F013` incomplete pending evaluator review.
- Recovery: final `./init.sh` passed harness verification, project compile, full project tests, dry-run smoke, and fake-backend smoke.
- Logs: initial `python ...` commands failed because this environment has no `python` shim; rerun with `python3` passed. This is an environment detail, not a product failure, because root `./init.sh` already uses an available Python runtime.
- External behavior verification: Picovoice official Python docs were checked for the Porcupine API contract: `pvporcupine.create(access_key=..., keywords=[...], sensitivities=[...])`, `process(pcm)` returning a keyword index or `-1`, and engine `frame_length`, `sample_rate`, and `delete()` methods.
- Capability gaps: `PICOVOICE_ACCESS_KEY` is a required user capability for the real wake-word path. F013 makes it durable through `.env.example`, diagnostics, README setup/troubleshooting, and runtime configuration; automated tests intentionally use fake engines and do not require the credential.

## Failure Analysis

- Failure domain: none
- Failure summary: No implementation failure or blocked capability was encountered during this manual coding pass. The missing `python` shim was handled by using `python3`, consistent with the repository recovery environment.
- Harness improvement: Not required; manual fallback was explicitly requested by the interactive Coding Agent prompt, run evidence was recorded, and evaluator gating remains in place.
- Follow-up feature: None

## Files Changed

- `.agent-harness/progress.md`
- `.agent-harness/runs/F013-manual-coding.md`
- `.env.example`
- `README.md`
- `requirements.txt`
- `src/audio_input.py`
- `src/config.py`
- `src/main.py`
- `src/wake_word.py`
- `tests/test_audio_input.py`
- `tests/test_config.py`
- `tests/test_documentation.py`
- `tests/test_main.py`
- `tests/test_openai_client.py`
- `tests/test_state_machine.py`
- `tests/test_wake_word.py`

## Evaluator Result

Awaiting Evaluator Agent review. Do not mark F013 done until a durable evaluator run records the exact `EVAL_PASS: F013` line.

## Follow-Up

- Run Evaluator Agent for F013.

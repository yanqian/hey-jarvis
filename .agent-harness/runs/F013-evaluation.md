# Run Record: F013 - Switch wake-word runtime to Porcupine

## Summary

- Date: 2026-07-03
- Agent role: Evaluator Agent
- Feature: F013 - Switch wake-word runtime to Porcupine
- Result: Accepted.

## Repository State

- Starting commit: `414fa12 F010-F011 Add wake debug probes`
- Ending commit: not committed
- Working tree status: F012/F013 implementation and evidence files are uncommitted; unrelated local audio artifacts are present under `tmp/` and were not modified.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_wake_word tests.test_config tests.test_main tests.test_audio_input tests.test_documentation
.agent-harness/scripts/validate-feature.sh F013
rg -n "prepare-wake-word|openwakeword|openWakeWord|onnxruntime|ONNX|wake_word_models" README.md .env.example requirements.txt src tests
```

## Evidence

- Tests: `./init.sh` passed harness verification, project compile, 54 project tests, dry-run smoke, and fake-backend smoke.
- Tests: focused F013 suite passed 33 tests covering Porcupine loader arguments, PCM conversion, frame-size validation, detector cleanup, config/diagnostics, documentation, live debug, file replay, and microphone frame defaults without a real microphone or Picovoice AccessKey.
- Feature validation: `.agent-harness/scripts/validate-feature.sh F013` passed with F013 still `in_progress` and `passes=false`, ready for evaluator-gated completion.
- External behavior verification: Picovoice Python Quick Start and API docs confirm `pvporcupine.create(access_key=..., keywords=[...], sensitivities=[...])`, AccessKey requirement, `frame_length`, `sample_rate`, `process(pcm) -> int`, `-1` for no detection, and `delete()` cleanup. Sources: https://picovoice.ai/docs/quick-start/porcupine-python/ and https://picovoice.ai/docs/api/porcupine-python/.
- Acceptance: `.agent-harness/progress.md` and `.agent-harness/runs/F013-manual-coding.md` record the openWakeWord blocker after Hey Jarvis and Alexa tests failed to wake reliably.
- Acceptance: active runtime code uses `pvporcupine`, `PICOVOICE_ACCESS_KEY`, configured keyword, sensitivity, engine frame length, and engine sample rate; active diagnostics and docs no longer require openWakeWord, onnxruntime, or ONNX model preparation.
- Capability gaps: `PICOVOICE_ACCESS_KEY` is a required user capability and is made durable through `.env.example`, diagnostics, README setup/troubleshooting, and fake-engine tests. No missing required capability was bypassed.

## Failure Analysis

- Failure domain: none
- Failure summary: No evaluator failure found.
- Harness improvement: Not required; manual fallback was recorded, evaluator gating was preserved, and durable evaluator evidence is now present.
- Follow-up feature: None

## Files Changed

- `.agent-harness/runs/F013-evaluation.md`

## Evaluator Result

```text
EVAL_PASS: F013
```

## Follow-Up

- Mark F013 done only as part of the harness evaluator-gated state transition.

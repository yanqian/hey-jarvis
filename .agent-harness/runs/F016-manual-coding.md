# Run Record: F016 - Keep assistant alive after empty transcription

## Summary

- Date: 2026-07-04
- Agent role: Manual Coding Agent fallback
- Feature: F016 - Keep assistant alive after empty transcription
- Result: Implementation completed by manual fallback; evaluator review recorded separately.

## Repository State

- Starting commit: `151db42 F015 Switch Alexa wake runtime to TFLite`
- Ending commit: not committed
- Working tree status: pre-existing uncommitted deployment documentation edits, local debug artifacts, `.DS_Store`, and audio files were present and preserved.

## User-Observed Failure

The real assistant returned successfully to `WAIT_WAKE`, detected another wake event, recorded `251` chunks until `stopped_by=max_duration`, then received HTTP 200 from OpenAI transcription but crashed with:

```text
src.openai_client.OpenAIClientError: OpenAI transcription returned empty text
```

This was not a manual stop. It was an unhandled recoverable OpenAI client error inside `VoiceAssistantStateMachine.run_once()`.

## Commands Run

```bash
git log --oneline -20
./init.sh
python3 -m unittest tests.test_state_machine
python3 -m unittest tests.test_documentation
python3 -m unittest tests.test_openai_client
```

## Evidence

- Code: `src/state_machine.py` now catches `OpenAIClientError` from transcription, chat, and text-to-speech stages, logs the current state and error, transitions back to `WAIT_WAKE`, and returns an `AssistantLoopResult` with the recoverable error text.
- Code: downstream stages are skipped after a failed prerequisite stage. Empty transcription does not call chat, TTS, or playback.
- Safety: unexpected non-OpenAI exceptions are not broadly swallowed; the focused test proves they still propagate.
- Tests: `python3 -m unittest tests.test_state_machine` passed 6 tests, including empty transcription recovery, chat error recovery, TTS error recovery, unexpected exception propagation, wake-debug logging, and the successful full loop.
- Tests: `python3 -m unittest tests.test_documentation` passed 3 tests after README and deployment troubleshooting updates.
- Tests: `python3 -m unittest tests.test_openai_client` passed 6 tests, preserving OpenAI client error behavior at the boundary.

## Failure Analysis

- Failure domain: none
- Failure summary: The state machine treated empty transcription as fatal because it did not catch the project-owned `OpenAIClientError` raised by the OpenAI client boundary.
- Harness improvement: Not required; this was a product robustness bug with deterministic tests and durable run evidence.
- Follow-up feature: None

## Files Changed

- `.agent-harness/SPEC.md`
- `.agent-harness/feature_list.json`
- `.agent-harness/progress.md`
- `.agent-harness/runs/F016-manual-coding.md`
- `.agent-harness/runs/F016-evaluation.md`
- `DEPLOYMENT.md`
- `README.md`
- `src/state_machine.py`
- `tests/test_state_machine.py`

## Evaluator Result

Awaiting evaluator record in `.agent-harness/runs/F016-evaluation.md`.

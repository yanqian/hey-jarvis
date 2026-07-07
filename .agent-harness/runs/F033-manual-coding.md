# F033 Manual Coding Evidence

## Context

Manual Coding Agent fallback for selected feature `F033` because this prompt was
run interactively rather than by the orchestrator adapter. The selected feature
was already `in_progress` with one attempt when this run started.

F033 addresses question recordings that continue to `MAX_RECORD_SECONDS` after
normal 4-5 second utterances when steady background noise is too high for the
old hard-coded recorder silence threshold.

## Implementation

- Added `RECORDING_SILENCE_RMS` configuration with a conservative default of
  `750`, typed environment loading, validation, `.env.example`, README,
  deployment, and manual-testing documentation.
- Passed `settings.recording_silence_rms` into question recording from the
  state machine without changing wake detection, ARMED speech detection,
  transcription, chat/tool routing, TTS, or playback behavior.
- Replaced strictly consecutive recorder silence detection with a
  recent-window rule that treats steady below-threshold background and
  occasional moderate noisy chunks as end-of-speech, while speech-like RMS
  chunks clear the silence window and extend recording.
- Preserved `stopped_by=silence`, `stopped_by=max_duration`, and
  `stopped_by=source_exhausted` result semantics without logging raw audio or
  secrets.
- Added synthetic PCM tests for noisy-background stopping, speech-like chunk
  extension, max-duration safety, configuration validation, state-machine
  wiring, and documentation coverage.

## Verification

```text
./init.sh
python3 -m unittest tests.test_config tests.test_recorder tests.test_state_machine
python3 -m unittest tests.test_config tests.test_recorder tests.test_state_machine tests.test_documentation
```

Focused tests passed before progress and evidence updates. Final `./init.sh`
must still pass after all coding-state updates.

## Capability Gap Assessment

No capability gap was introduced. The implementation is deterministic and uses
synthetic PCM fixtures; it does not require live microphone access, OpenAI,
speaker playback, network access, a new VAD dependency, or new runtime
credentials.

## Failure Domain And Harness Improvement

Failure domain: none for this Coding Agent run. No harness improvement is
required; this is a project implementation change within the planned F033
scope.

## Evaluator Handoff

F033 is implemented but not marked complete by the Coding Agent. Evaluator
evidence with `EVAL_PASS: F033` is still required before `feature_list.json`
should be marked done.

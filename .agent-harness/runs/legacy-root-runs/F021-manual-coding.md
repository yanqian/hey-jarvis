# F021 Manual Coding Run

Date: 2026-07-05

Role: Coding Agent

Feature: F021 - Add wake acknowledgement before recording

## Invocation

Manual Coding Agent fallback. The user invoked the Coding Agent prompt interactively for selected feature `F021`, so this run did not use unattended role adapters. Evaluator gating is not bypassed; this run records implementation evidence and leaves the feature awaiting evaluator review.

## Summary

Implemented wake acknowledgement before question recording:

- Added documented acknowledgement configuration defaults: enabled state, text `在呢`, audio path `tmp/ack.mp3`, and drain duration.
- Added diagnostics and real-startup fail-fast guidance when acknowledgement playback is enabled but the prepared audio file is missing.
- Added `python -m src.main --prepare-acknowledgement` to generate the configured acknowledgement audio once through the existing OpenAI TTS boundary.
- Added `ACK_PLAYING` between `WAIT_WAKE` and `RECORDING`; normal wake handling plays the prepared local file, drains microphone residue, then starts the existing recorder.
- Updated fake-backend smoke coverage, focused tests, README, deployment notes, `.env.example`, and manual acceptance cases.

## Verification

Commands run:

```bash
./init.sh
python3 -m unittest tests.test_config tests.test_state_machine tests.test_main
python3 -m src.main --fake-backend
python3 -m unittest discover tests
python3 -m src.main --dry-run && python3 -m src.main --fake-backend
```

All listed commands passed during implementation. Final `./init.sh` verification is required after this run record is written.

## Failure Domain

Primary failure domain: none

No implementation failure or blocked condition occurred in this Coding Agent run.

## Harness Improvement Assessment

Harness improvement required: no

The manual fallback was explicitly requested by the interactive Coding Agent prompt. The harness rules were sufficient: startup protocol, run evidence, capability-gap checks, example-boundary rules, and evaluator handoff were followed.

## Capability Gap Assessment

Capability gaps: none

Live OpenAI TTS is required only for the user-run acknowledgement preparation command and is already a documented runtime capability through `OPENAI_API_KEY` and the existing OpenAI client boundary. Automated verification uses fakes and does not require live credentials, microphone access, speakers, or generated audio artifacts.

## Example Boundary Assessment

`examples/` was not changed.

## Evaluator Handoff

F021 remains awaiting evaluator review. The evaluator should verify the acceptance criteria against the implementation and record `EVAL_PASS: F021` or `EVAL_FAIL: F021: <reason>` in run evidence before the feature is marked done.

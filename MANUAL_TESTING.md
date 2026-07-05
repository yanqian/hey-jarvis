# Manual Testing

This document tracks manual acceptance tests for the Hey Jarvis macOS MVP.
Automated recovery checks cover dependency-free logic. These tests cover the
real microphone, wake-word model, OpenAI calls, and macOS playback path.

## Prerequisites

Run the recovery and deployment checks before manual acceptance:

```bash
./init.sh
python -m src.main --diagnose
```

All diagnostic errors should be fixed before running the real assistant. The
real path also requires macOS microphone permission for the launching app,
prepared wake-word models, `afplay`, and a valid `OPENAI_API_KEY`.

## Recording Behavior

The MVP records after the wake word is detected and stops when either condition
is reached:

- `SILENCE_SECONDS`, default `1.5`, of consecutive audio below the built-in RMS
  silence threshold.
- `MAX_RECORD_SECONDS`, default `20`, total recording duration.

This means recording is not expected to always wait for 20 seconds. It should
stop shortly after the user finishes speaking. If a 10-15 second question is
cut off early, check the runtime log line:

```text
State RECORDING: wrote ... chunks to tmp/input.wav; stopped_by=...
```

Interpretation:

- `stopped_by=silence`: the recorder heard enough consecutive low-level audio
  to treat the question as finished. This can happen during long pauses, when
  the speaker is too quiet, or when the microphone level is low.
- `stopped_by=max_duration`: the question reached `MAX_RECORD_SECONDS`.
- `stopped_by=source_exhausted`: the audio source ended unexpectedly; this is
  not expected during real microphone operation.

For manual acceptance, inspect `tmp/input.wav` after a failed recording. It
should contain the complete question with usable volume. If it is clipped,
nearly silent, or missing the later part of the question, record the test as a
failure and note the `stopped_by` value.

If the recorder waits a long time after the user stops speaking, the room or
microphone may still be above the built-in silence threshold, so the silence
timer does not complete and recording continues until `MAX_RECORD_SECONDS`. If
the recorder cuts off a long question, the opposite happened: a pause or
low-volume section was counted as `SILENCE_SECONDS` of silence.

For M003 retesting, temporarily try:

```text
SILENCE_SECONDS=3.0
MAX_RECORD_SECONDS=30
```

This gives long questions more room for natural pauses. If the question still
cuts off with `stopped_by=silence`, record the result as a failure; the next
product change should make recording silence behavior more observable and
configurable.

## Acceptance Standard

The MVP is acceptable when:

- Wake-word detection succeeds at least 8 out of 10 attempts in a normal local
  environment.
- Five complete question-answer loops run without restarting the process.
- Empty transcription, network/API failures, and no-speech-after-wake cases
  return to `WAIT_WAKE` without crashing.
- `tmp/input.wav` contains the complete spoken question for normal and long
  question tests.
- `tmp/output.mp3` contains the latest synthesized answer after successful
  loops.

## Test Cases

| ID | Area | Steps | Expected result |
| --- | --- | --- | --- |
| M001 | Full MVP loop | Start `python -m src.main`, say `Alexa, what is two plus two?` | Assistant wakes, records, transcribes, answers, plays audio, and returns to `WAIT_WAKE`. |
| M002 | Consecutive loops | After M001 completes, ask `Alexa, what is the capital of France?` without restarting. | Second loop completes and returns to `WAIT_WAKE`. |
| M003 | Long question | Ask a 10-15 second question with natural speech. | Recording includes the full question and does not stop before the question is complete. |
| M004 | Short question | Ask `Alexa, time?` or `Alexa, hello?` | Assistant records enough audio to transcribe or returns cleanly to `WAIT_WAKE` on empty transcription. |
| M005 | Wake normal distance | Say `Alexa` from roughly 0.5-1 meter away. | Wake word triggers reliably. |
| M006 | Wake far distance | Say `Alexa` from roughly 2-3 meters away. | Wake behavior is understandable from debug scores; failure should show low RMS/score rather than a crash. |
| M007 | Wake background noise | Play light background audio and say `Alexa`. | Clear wake phrases trigger; unrelated background speech should not frequently trigger. |
| M008 | No false wake | Speak several sentences without saying `Alexa`. | Assistant stays in `WAIT_WAKE`. |
| M009 | Wake success rate | Try 10 clear `Alexa` wake attempts. | At least 8 attempts trigger. |
| M010 | Natural stop | Ask a normal question, then stay quiet. | Recording stops after a short silence and logs `stopped_by=silence`. |
| M011 | Max duration | Speak continuously longer than `MAX_RECORD_SECONDS`. | Recording stops with `stopped_by=max_duration`; process keeps running. |
| M012 | Wake then silence | Say only `Alexa`, then remain silent. | Empty or unusable transcription is logged as recoverable and the assistant returns to `WAIT_WAKE`. |
| M013 | Input WAV quality | After any question, inspect or play `tmp/input.wav`. | File contains the current question, in mono 16 kHz 16-bit WAV format, with usable volume. |
| M014 | Temporary network failure | Disconnect network after wake and ask a question. | OpenAI failure is logged as recoverable and assistant returns to `WAIT_WAKE`. |
| M015 | Invalid API key | Run with an invalid `OPENAI_API_KEY`. | Error is clear and does not leave the app in an ambiguous state. |
| M016 | TTS output | Complete a successful question-answer loop and inspect `tmp/output.mp3`. | File exists and contains the latest spoken answer. |
| M017 | Idle stability | Leave the assistant idle for 10-15 minutes. | Process remains alive, does not repeatedly false-trigger, and does not consume abnormal CPU. |
| M018 | Multi-loop stability | Complete 5-10 question-answer loops. | Every loop returns to `WAIT_WAKE`. |
| M019 | Ctrl-C shutdown | Press `Ctrl-C` while the assistant is waiting. | Process exits cleanly with no unexpected traceback. |
| M020 | Playback overlap | Speak during answer playback. | Current MVP may not interrupt playback, but it should not crash. |
| M021 | Restart recovery | Stop the process and start it again without cleaning `tmp/`. | Assistant starts normally and can complete another loop. |
| M022 | Post-playback false wake | Complete a successful answer, then say nothing after playback finishes. | The assistant drains the post-playback microphone window, waits for quiet audio, stays in `WAIT_WAKE`, and does not enter `RECORDING`. |

## Known Manual Failures

### F017 Post-Playback False Wake

Observed failure:

```text
State PLAYING: playback finished
Transition PLAYING -> WAIT_WAKE
State WAIT_WAKE: ready for the next wake word
State WAIT_WAKE: listening for the alexa wake word
Microphone input overflowed; the current audio chunk may be incomplete
State WAIT_WAKE: wake word detected
Transition WAIT_WAKE -> RECORDING
State RECORDING: wrote 251 chunks to tmp/input.wav; stopped_by=max_duration
Transition RECORDING -> TRANSCRIBE
Recoverable OpenAI error in state TRANSCRIBE: OpenAI transcription returned empty text
```

Expected retest after F017: after playback, say nothing. The app should log
post-playback suppression, should not call wake detection for discarded chunks,
and should remain in `WAIT_WAKE`. If it still wakes by itself, increase
`POST_PLAYBACK_WAKE_COOLDOWN_SECONDS` and capture the logs with the current
`WAKE_CONFIRMATION_FRAMES` value.

### F018 Post-Cooldown Residual Wake

Observed failure after F017:

```text
State WAIT_WAKE: suppressing post-playback wake detection for 1.00s
Microphone input overflowed; the current audio chunk may be incomplete
State WAIT_WAKE: discarded 13 post-playback microphone chunks
State WAIT_WAKE: ready for the next wake word
State WAIT_WAKE: listening for the alexa wake word
State WAIT_WAKE: wake word candidate 1/2
State WAIT_WAKE: wake word detected
Transition WAIT_WAKE -> RECORDING
```

Expected retest after F018: after the fixed cooldown, the app should continue
suppressing wake decisions until it observes `POST_PLAYBACK_QUIET_SECONDS` of
audio below `POST_PLAYBACK_QUIET_RMS`. Residual wake-positive chunks during
this quiet gate should appear in the `max_suppressed_score` summary and must not
enter `RECORDING`.
Increase `POST_PLAYBACK_QUIET_SECONDS` or
`POST_PLAYBACK_MAX_SUPPRESSION_SECONDS` if the room or speaker echo stays loud
after playback.

## Running One Test At A Time

For each manual test, record:

- Test ID.
- Pass or fail.
- Relevant command.
- Observed logs, especially state transitions and `stopped_by`.
- Whether `tmp/input.wav` and `tmp/output.mp3` match the expected current run.
- Any environment changes such as `SILENCE_SECONDS`, `MAX_RECORD_SECONDS`, or
  `WAKE_THRESHOLD`.
- Any post-playback settings such as `POST_PLAYBACK_WAKE_COOLDOWN_SECONDS`,
  `POST_PLAYBACK_QUIET_SECONDS`, `POST_PLAYBACK_QUIET_RMS`,
  `POST_PLAYBACK_MAX_SUPPRESSION_SECONDS`, or `WAKE_CONFIRMATION_FRAMES`.

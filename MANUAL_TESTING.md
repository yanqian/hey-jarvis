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
When `WAKE_ACKNOWLEDGEMENT_ENABLED=1`, it also requires prepared acknowledgement
audio from:

```bash
python -m src.main --prepare-acknowledgement
```

## Recording Behavior

The MVP enters `ARMED` after the wake word is detected, the acknowledgement
plays, and the acknowledgement drain window completes. Recording starts only
after a recent window contains enough non-overflow, non-clipped chunks above
`max(ARMED_MIN_RMS, noise_floor * ARMED_SNR_MULTIPLIER)`. `ARMED_VOICE_RMS`
is a legacy fallback for `ARMED_MIN_RMS`. The assistant preserves
`ARMED_PRE_ROLL_SECONDS` of recent audio before recording so the first words are
not dropped, and logs `armed_summary` on timeout or `armed_trigger` on recording
start. If speech is not detected within
`ARMED_NO_SPEECH_TIMEOUT_SECONDS`, the assistant returns to `WAIT_WAKE` without
recording, transcription, chat/tool routing, TTS, or playback. Once recording
starts, it stops when either condition is reached:

- `SILENCE_SECONDS`, default `1.5`, of recent-window audio mostly below
  `RECORDING_SILENCE_RMS`, default `750`.
- `MAX_RECORD_SECONDS`, default `20`, total recording duration.

This means recording is not expected to always wait for 20 seconds. It should
stop shortly after the user finishes speaking, even with steady low or moderate
background noise. If a 10-15 second question is cut off early, check the
runtime log line:

```text
State RECORDING: wrote ... chunks to tmp/input.wav; stopped_by=...
```

Interpretation:

- `stopped_by=silence`: the recorder heard enough recent low-level audio to
  treat the question as finished. This can happen during long pauses, when the
  speaker is too quiet, or when the microphone level is low.
- `stopped_by=max_duration`: the question reached `MAX_RECORD_SECONDS`.
- `stopped_by=source_exhausted`: the audio source ended unexpectedly; this is
  not expected during real microphone operation.

For manual acceptance, inspect `tmp/input.wav` after a failed recording. It
should contain the complete question with usable volume. If it is clipped,
nearly silent, or missing the later part of the question, record the test as a
failure and note the `stopped_by` value.

If the recorder waits a long time after the user stops speaking, the room or
microphone may still be above `RECORDING_SILENCE_RMS`, so the recent-window
silence rule does not complete and recording continues until
`MAX_RECORD_SECONDS`. If the recorder cuts off a long question, the opposite
happened: a pause or low-volume section was counted as `SILENCE_SECONDS` of
silence.

For M003 retesting, temporarily try:

```text
SILENCE_SECONDS=3.0
MAX_RECORD_SECONDS=30
RECORDING_SILENCE_RMS=750
```

This gives long questions more room for natural pauses. If the question still
cuts off with `stopped_by=silence`, lower `RECORDING_SILENCE_RMS` only if the
room is genuinely quiet and the speaker is loud enough; otherwise record the
result as a failure.

## Current ARMED Real-Test Findings

The acknowledgement boundary now uses a conservative guard instead of blindly
discarding a fixed window. With the defaults, logs begin with `State
ACK_PLAYING: guarding acknowledgement microphone residue for 0.60s` and end
with discarded/preserved chunk counts, observed quiet time, maximum RMS, and
maximum peak. A small late non-quiet tail may seed ARMED pre-roll, but guard
audio never triggers recording by itself.

If a transcript is missing the first syllable, such as spoken `一加一等于几`
being transcribed as `加一等于几`, inspect the preceding `armed_trigger` log.
The normal expectation is that immediate speech after `在呢` retains its first
syllable in `tmp/input.wav`. Inspect the acknowledgement guard summary for a
non-zero preserved count and the later `armed_trigger` for
`baseline_ready=true`, `baseline_chunks`, and `baseline_seconds`.

A no-speech wake should normally produce an ARMED timeout:

```text
armed_summary ... result=no_speech_timeout
```

The previous bad pattern was an early recording start with a cold noise floor:

```text
armed_trigger after=0.32s ... noise_floor=0.0 ... voiced_window=4/4 ... result=recording_started
State RECORDING: wrote ... chunks to tmp/input.wav; stopped_by=max_duration
State TRANSCRIBE: local cancellation reason=empty_transcript
```

With defaults, ARMED cannot trigger until `baseline_ready=true`, and the latest
chunk must still be voiced. Saying only `Hey Jarvis` and remaining silent must
show `armed_summary ... result=no_speech_timeout`, return to `WAIT_WAKE`, and
must not enter `RECORDING`, transcription, routing, answer TTS, or playback.
Capture the guard summary, `armed_summary`, and any unexpected `State RECORDING`
line when reporting a regression.

Relevant default settings while testing:

```text
ARMED_NO_SPEECH_TIMEOUT_SECONDS=2.0
ARMED_MIN_RMS=750
ARMED_VOICE_RMS=750
ARMED_SNR_MULTIPLIER=2.5
ARMED_BASELINE_SECONDS=0.30
ARMED_BASELINE_MIN_CHUNKS=3
ARMED_REQUIRE_BASELINE=1
ARMED_LAST_CHUNK_MUST_BE_VOICED=1
ACK_GUARD_ENABLED=1
ACK_GUARD_SECONDS=0.60
ACK_GUARD_MIN_QUIET_SECONDS=0.16
ACK_GUARD_QUIET_RMS=600
ACK_GUARD_MAX_BUFFER_SECONDS=1.00
```

Manual case 1: say only `Hey Jarvis`, allow `在呢` to play, and remain silent.
Confirm the guard summary is followed by `armed_summary ...
result=no_speech_timeout` and no `State RECORDING` line. Manual case 2: say
`Hey Jarvis`, then begin `一加一等于几` immediately after `在呢`. Confirm
`tmp/input.wav` contains the full question under normal timing, the guard log
reports any preserved boundary chunks, and `armed_trigger` shows
`baseline_ready=true` before recording starts.

## Acceptance Standard

### Optional VAD checks

Keep `VAD_BACKEND=disabled` first and confirm the F036 silence and immediate
request cases behave unchanged. Then install `webrtcvad`, set
`VAD_BACKEND=webrtc`, and repeat these checks:

1. Say `Hey Jarvis`, let the acknowledgement play, do not speak, and make
   keyboard, fan, or light object noise. ARMED should return to `WAIT_WAKE`
   without `RECORDING`; its summary should show low VAD evidence or
   `vad_ok=false`.
2. Play unrelated background human speech without intentionally saying the wake
   phrase. There should be no wake, ARMED recording, chat, or TTS. If the wake
   model itself fires, capture both wake and ARMED VAD diagnostics.
3. Say `Hey Jarvis` and ask a normal question shortly after `在呢`. The first
   syllable should remain in `tmp/input.wav`; `armed_trigger` should show
   `baseline_ready=true`, `vad_ok=true`, and its VAD ratio.
4. With `RECORDING_VAD_ENABLED=1`, speak a question with a short natural pause.
   Recording should continue after the pause, then finish on sustained
   non-voice silence rather than `MAX_RECORD_SECONDS`.

The relevant controls are `VAD_BACKEND`, `VAD_MODE`,
`ARMED_VAD_REQUIRED_RATIO`, `ARMED_VAD_MIN_FRAMES`, optional
`WAKE_VAD_THRESHOLD`, `RECORDING_VAD_ENABLED`,
`RECORDING_VAD_END_RATIO`, `RECORDING_VAD_SPEECH_RATIO`,
`RECORDING_HANGOVER_SECONDS`, and `RECORDING_END_SILENCE_SECONDS`.

The MVP is acceptable when:

- Wake-word detection succeeds at least 8 out of 10 attempts in a normal local
  environment.
- Five complete question-answer loops run without restarting the process.
- The assistant plays the configured wake acknowledgement after wake detection
  and does not include that acknowledgement audio in `tmp/input.wav`.
- Empty transcription, network/API failures, and no-speech-after-wake cases
  return to `WAIT_WAKE` without crashing.
- `tmp/input.wav` contains the complete spoken question for normal and long
  question tests.
- `tmp/output.mp3` contains the latest synthesized answer after successful
  loops.

## Test Cases

| ID | Area | Steps | Expected result |
| --- | --- | --- | --- |
| M001 | Full MVP loop | Start `python -m src.main`, say `Hey Jarvis`, wait for the acknowledgement such as `在呢`, then ask `what is two plus two?` | Assistant wakes, plays acknowledgement, drains microphone residue, records, transcribes, answers, plays audio, and returns to `WAIT_WAKE`. |
| M002 | Consecutive loops | After M001 completes, say `Hey Jarvis`, wait for acknowledgement, then ask `what is the capital of France?` without restarting. | Second loop completes and returns to `WAIT_WAKE`. |
| M003 | Long question | Ask a 10-15 second question with natural speech. | Recording includes the full question and does not stop before the question is complete. |
| M004 | Short question | Ask `Hey Jarvis, time?` or `Hey Jarvis, hello?` | Assistant records enough audio to transcribe or returns cleanly to `WAIT_WAKE` on empty transcription. |
| M005 | Wake normal distance | Say `Hey Jarvis` from roughly 0.5-1 meter away. | Wake word triggers reliably. |
| M006 | Wake far distance | Say `Hey Jarvis` from roughly 2-3 meters away. | Wake behavior is understandable from debug scores; failure should show low RMS/score rather than a crash. |
| M007 | Wake background noise | Play light background audio and say `Hey Jarvis`. | Clear wake phrases trigger; unrelated background speech should not frequently trigger. |
| M008 | No false wake | Speak several sentences without saying `Hey Jarvis`. | Assistant stays in `WAIT_WAKE`. |
| M009 | Wake success rate | Try 10 clear `Hey Jarvis` wake attempts. | At least 8 attempts trigger. |
| M010 | Natural stop | Ask a normal question, then stay quiet. | Recording stops after a short silence and logs `stopped_by=silence`. |
| M011 | Max duration | Speak continuously longer than `MAX_RECORD_SECONDS`. | Recording stops with `stopped_by=max_duration`; process keeps running. |
| M012 | Wake then silence | Say only `Hey Jarvis`, wait for acknowledgement, then remain silent. | Assistant enters `ARMED`, logs local cancellation such as `no_speech_after_wake`, and returns to `WAIT_WAKE` without recording, transcription, answer generation, TTS, or playback. |
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
| M023 | Wake acknowledgement boundary | Say `Hey Jarvis`, wait for acknowledgement, then ask a normal question. Inspect `tmp/input.wav`. | The acknowledgement plays from the prepared local file, `ARMED` starts after the drain window, and `tmp/input.wav` contains the user question without acknowledgement audio. |
| M024 | Open-Meteo weather | Run `python -m src.main --text "明天天气怎么样"` and `python -m src.main --text "weather in Tokyo today"` with network access. Optionally ask the same questions through the voice loop. | Text debug routes to `weather`, returns `result_status=success`, names `Open-Meteo`, uses `DEFAULT_LOCATION=Singapore` when no location is spoken, and does not fall back to chat speculation on provider errors. |
| M025 | Frankfurter FX | Run `python -m src.main --text "100 USD to SGD"` and `python -m src.main --text "100美元兑人民币汇率是多少"` with network access. Optionally ask the same questions through the voice loop. | Text debug routes to `fx`, returns `result_status=success`, names Frankfurter, includes rate date and converted amount, says the answer is a reference rate rather than a bank cash or trade quote, and does not fall back to chat speculation on provider errors. |
| M026 | Finnhub stock quote | Set `FINNHUB_API_KEY`, then run `python -m src.main --text "AAPL stock price"` and `python -m src.main --text "苹果股价多少"` with network access. Optionally ask the same questions through the voice loop. | Text debug routes to `stock`, returns `result_status=success`, uses symbol `AAPL`, names Finnhub, includes current price, change, percent change, timestamp, and market-data caveats, and does not fall back to chat speculation on provider errors. |
| M027 | Tool answer naturalization | With `TOOL_ANSWER_NATURALIZATION=1`, ask successful weather, FX, and stock questions through the voice loop. Also run the same questions with `python -m src.main --text ...`. | Voice answers may be worded more naturally but preserve provider numbers, units, timestamps, sources, caveats, and advice disclaimers. Text debug prints `raw_answer` and `naturalization_status=not_run_text_debug` without calling OpenAI. Failures, realtime refusals, local time, and calculator answers remain raw. |
| M028 | Cancel phrases | Say `Hey Jarvis`, wait for acknowledgement, then say `取消`, `没事`, `不用了`, `算了`, `stop`, `cancel`, or `never mind`. | Assistant treats the transcript as local cancellation and returns to `WAIT_WAKE` without chat/tool routing, answer TTS, playback, or chat-history changes. |
| M030 | Noisy cancel phrases | Say `Hey Jarvis`, wait for acknowledgement, then say short noisy variants such as `没事了`, `没事不用了`, `没事 谢谢`, `没事 后面有声音`, `取消吧`, `算了算了`, or `stop please`. Then try `没事的话帮我查天气`, `取消我明天的闹钟`, or `cancel my alarm tomorrow`. | Short noisy cancel variants return to `WAIT_WAKE` without chat/tool routing, answer TTS, playback, or chat-history changes, and logs show `match_mode=noisy_suffix`. Command-like continuations are not locally cancelled. |
| M031 | Post-cancel wake suppression | Say `Hey Jarvis`, wait for acknowledgement, then say `算了算了` or remain silent through the ARMED timeout. Say nothing while speaker/microphone residue settles, then later say `Hey Jarvis` again and ask a normal question. | Local cancellation logs post-cancellation suppression, discarded chunks, quiet-gate status, and `max_suppressed_score`; residual wake-positive chunks do not trigger a second acknowledgement loop, and the later intentional wake works after quiet. |
| M032 | Spoken Chinese cancel variants | Say `Hey Jarvis`, wait for acknowledgement, then say `不用啦`, `不用不用`, `不用不用了`, `不要了`, `没事儿`, `没事没事儿`, or `没事儿没事儿`. Then try `不用了帮我查天气`, `没事的话帮我查天气`, `取消我明天的闹钟`, or `不要取消我明天的闹钟`. | Colloquial cancel variants return through local cancellation and F031 post-cancellation suppression without chat/tool routing, answer TTS, playback, or chat-history changes. Command-like continuations are not locally cancelled and short non-cancel transcripts log `match_decision=not_cancelled`. |

## Known Manual Failures

### F017 Post-Playback False Wake

Observed failure:

```text
State PLAYING: playback finished
Transition PLAYING -> WAIT_WAKE
State WAIT_WAKE: ready for the next wake word
State WAIT_WAKE: listening for the hey jarvis wake word
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
State WAIT_WAKE: listening for the hey jarvis wake word
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

### F031 Post-Cancel Residual Wake

Observed failure after F030:

```text
State TRANSCRIBE: transcript cancellation normalized_transcript='算了算了' match_mode=noisy_suffix
State TRANSCRIBE: local cancellation reason=cancel_phrase
Transition TRANSCRIBE -> WAIT_WAKE
State WAIT_WAKE: ready for the next wake word
State WAIT_WAKE: listening for the hey jarvis wake word
State WAIT_WAKE: wake word detected
Transition WAIT_WAKE -> ACK_PLAYING
State ACK_PLAYING: played wake acknowledgement from var/ack.mp3
Transition ACK_PLAYING -> ARMED
State ARMED: no speech detected
```

Expected retest after F031: after local cancellation, the app should log
post-cancellation suppression and continue suppressing wake decisions until it
observes quiet audio. Residual wake-positive chunks should appear in the
`max_suppressed_score` summary and must not trigger another acknowledgement
cycle. A fresh `Hey Jarvis` after the quiet gate should still wake normally.

## Running One Test At A Time

For each manual test, record:

- Test ID.
- Pass or fail.
- Relevant command.
- Observed logs, especially state transitions and `stopped_by`.
- Whether `tmp/input.wav` and `tmp/output.mp3` match the expected current run.
- Any environment changes such as `SILENCE_SECONDS`, `MAX_RECORD_SECONDS`, or
  `WAKE_THRESHOLD`.
- Any armed/cancellation settings such as `ARMED_NO_SPEECH_TIMEOUT_SECONDS`,
  `ARMED_MIN_RMS`, `ARMED_SNR_MULTIPLIER`, `ARMED_VOICE_WINDOW_SECONDS`,
  `ARMED_VOICE_REQUIRED_RATIO`, `ARMED_CLIP_REJECT_PEAK`,
  `ARMED_PRE_ROLL_SECONDS`, `ARMED_VOICE_RMS`, `MIN_VALID_SPEECH_SECONDS`,
  `MIN_TRANSCRIPT_LENGTH`, or `CANCEL_PHRASES`.
- Any post-playback settings such as `POST_PLAYBACK_WAKE_COOLDOWN_SECONDS`,
  `POST_PLAYBACK_QUIET_SECONDS`, `POST_PLAYBACK_QUIET_RMS`,
  `POST_PLAYBACK_MAX_SUPPRESSION_SECONDS`, or `WAKE_CONFIRMATION_FRAMES`.
- Any acknowledgement settings such as `WAKE_ACKNOWLEDGEMENT_ENABLED`,
  `WAKE_ACKNOWLEDGEMENT_AUDIO_PATH`, or `WAKE_ACKNOWLEDGEMENT_DRAIN_SECONDS`.

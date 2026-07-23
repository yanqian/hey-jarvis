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

## Wake acknowledgement overlap

Run `python -m src.main` and repeat each case at least three times with the same
question, such as `一加一等于几`:

1. Start near the end of the configured acknowledgement (`嗯` in the current
   local configuration) and continue beyond playback completion. The
   complete question prefix should be transcribed and answered.
2. Start exactly as `嗯` completes. The complete question should be captured
   without an ACK-boundary timeout.
3. Wait one second after `嗯`, then speak. This stable path must remain
   successful.
4. Do not speak after waking. ACK echo alone must end as
   `no_speech_after_wake` without recording or OpenAI.

Inspect the log for `playback handoff`, `quarantined_overlap_chunks=1`, a useful
`noise_seed_count`, and `noise_floor_has_samples=true` on `armed_trigger`.
Playback-only audio must not produce `recording_started`. Speech spoken entirely
before the acknowledgement finishes is not supported without acoustic echo cancellation.

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

The acknowledgement boundary now has a mandatory quiet gate. With the defaults,
logs begin with `State ACK_PLAYING: waiting for safe post-ACK boundary` and end
with `post_ack_quiet_observed`, suppressed/noise-seed chunk counts, maximum RMS
and peak, plus clipped/overflow counts. ARMED is not entered if the boundary
times out without quiet, and clipped or overflowed acknowledgement residue is
never added to recording pre-roll.

After `post_ack_quiet_observed=true`, clipped audio is treated differently from
ACK residue: it is preserved as possible user speech in pre-roll but cannot
trigger ARMED or update the noise floor. Overflowed chunks are skipped. A later
clipped/overflowed user chunk must not clear earlier words; if an 800ms pre-roll
collapses to only the final 240ms, record that as a regression.

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
ACK_GUARD_MIN_QUIET_SECONDS=0.16
ACK_GUARD_QUIET_RMS=900
ACK_GUARD_MAX_BUFFER_SECONDS=1.50
```

Manual case 1: say only `Hey Jarvis`, allow `在呢` to play, and remain silent.
Confirm the guard summary is followed by `armed_summary ...
result=no_speech_timeout` and no `State RECORDING` line. Manual case 2: say
`Hey Jarvis`, then begin `一加一等于几` immediately after `在呢`. Confirm
`tmp/input.wav` contains the full question under normal timing, the guard log
reports any preserved boundary chunks, and `armed_trigger` shows
`baseline_ready=true` before recording starts.

For the F040 playback-drain check, confirm each real acknowledgement logs
`playback microphone drain` before the post-ACK boundary summary. The drain
should consume the speaker-contaminated chunks while `afplay` is active and
report `completed=true`; the first post-ACK overflow should no longer be caused
by an unread playback backlog. Drained audio must not appear in
`tmp/input.wav`. After a successful synchronized drain, F041 hands subsequent
live audio directly into protected ARMED pre-roll without mandatory quiet
suppression. Confirm that `synchronized live handoff` and
`post_ack_synchronized=true` appear, then say `一加一等于几` immediately after
the acknowledgement and verify the full prefix is present. Legacy/fake players
without an observable playback handle must continue using the conservative
quiet-boundary fallback.

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
4. With `RECORDING_VAD_ENABLED=1`, first speak continuously until the
   `WAIT_WAKE -> RECORDING` transition is logged, then include a short natural
   pause before finishing the question. This checks recorder hangover after
   RECORDING has started: recording should continue after the pause, then finish
   on sustained non-voice silence rather than `MAX_RECORD_SECONDS`. It does not
   cover the unresolved ARMED case where a short prefix, a deliberate pause,
   and a later suffix may trigger only on the suffix after the prefix has left
   pre-roll.

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
| M048 | Recording VAD false-high endpoint | On Python 3.12 install `requirements-vad.txt`, set `VAD_BACKEND=webrtc` and `RECORDING_VAD_ENABLED=1`, ask five normal continuous questions, then stay quiet. | Every question logs `stopped_by=silence` after hangover plus roughly `RECORDING_END_SILENCE_SECONDS`, not `max_duration`; `recording_endpoint` may report nonzero `low_energy_high_vad_chunks`. F048 passed this check 5/5 on the tested microphone; repository-wide default enablement remains a separate product decision. |
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
| M040 | Drain microphone during acknowledgement | Start the real assistant, wake it five times, and inspect each ACK_PLAYING sequence while the local acknowledgement plays. | Each sequence logs a completed playback microphone drain before the post-ACK boundary; playback-time chunks never enter the recorded WAV, no playback process is left running, and the post-ACK boundary starts from current rather than queued acknowledgement audio. |
| M041 | Immediate speech after synchronized acknowledgement | On the real macOS path, say `Hey Jarvis` and begin `一加一等于几` immediately when the acknowledgement ends; repeat five times, then repeat once with silence and once with only a short click/tail sound. | Successful drains log `synchronized live handoff`; the full question prefix reaches `tmp/input.wav` without mandatory quiet suppression, five normal loops complete, and silence or a single tail sound returns locally without recording or OpenAI. |
| M047 | Stable knowledge versus realtime boundary | With `OPENAI_API_KEY` configured, ask `中国古代人的语言交流跟现在中国哪个省份的方言类似？`, then ask another broad stable question such as `粤语为什么保留入声？`, and finally ask `今天有什么新闻`. | Stable questions receive concise qualified best-effort answers in Chinese and do not stop at an internet-required refusal merely because comparison or uncertainty is involved. The assistant does not claim it browsed or checked sources. The current-news question uses the existing structured realtime refusal/provider boundary rather than model memory. |
| M057 | Realtime five-cycle acceptance | Set `BACKEND=realtime` and `REALTIME_OUTPUT_VOLUME=0.1`, launch once, click **Arm hands-free audio** once, and complete at least five real built-in-microphone/speaker wake cycles without another click. Across the cycles perform two-turn conversation, deliberately speak over a long answer, invoke `calculator`, and close using end phrase, idle timeout, explicit stop, or a bounded failure/cleanup path. After every close verify the Chrome microphone indicator clears and a new real `Hey Jarvis` still wakes. | Record per cycle: actual echo cancellation/noise suppression/auto gain/sample rate/channel count/output volume; wake-to-connected and response timing; self-echo false-interruption count; deliberate interruption result; errors; exit reason; microphone indicator cleared; and next-wake result. Pass requires 48 kHz mono with browser processing enabled on the tested Mac, no self-echo false interruption, prompt deliberate barge-in, bounded errors, and restoration to `WAIT_WAKE`. Do not record transcript text, credentials, or audio in committed evidence. If normal answers cancel themselves, lower `REALTIME_OUTPUT_VOLUME`; do not hide the failure or add client truncation. |
| M058 | Pipeline timing and current-turn language | Start with a fresh process. Ask `中国为什么参与朝鲜战争`, then `人脸识别的英文怎么读`, then `Why did China enter the Korean War?`. Inspect the successful loop logs after each answer. | The first answer is entirely concise Simplified Chinese. The second includes the requested English term or pronunciation but explains it in Chinese. The third is English even after Chinese history. Each loop logs ordered `pipeline_timing` stages and one `response_timing` summary; compare `recording`, `ready_to_play`, and the individual transcription/answer/TTS/playback durations to locate delay. No answer body, raw audio, API key, or provider secret appears in the timing lines. |
| M059 | RT003 assisted near-end barge-in eval | Configure and launch `BACKEND=realtime`, click **Arm hands-free audio** once, use the built-in microphone/speaker without headphones, ensure the private `wake` fixture exists, and run `python -m src.evals.realtime_barge_in live`. Be ready to speak, then press Enter at the readiness gate; only then does the runner wake, establish the session, and promptly request the long answer without spending session idle time on operator coordination. After the exact `response.created` marker, wait until counting is audible and immediately speak one natural interruption utterance. That utterance doubles as audible confirmation, so there is no second terminal/chat round trip. | A passing product run observes real near-end speech, reports the old answer as `cancelled` within 1000ms, waits for the continuation to complete, performs bounded stop/cleanup, and restores `wake_owned` with the wake microphone open. Closed input, operator cancellation, an answer ending before valid near-end speech, any missing event, excessive latency, early session close, or cleanup failure exits non-zero and still saves a precise sanitized FAIL result under `tmp/realtime-evals/`; it must not be relabeled as passing. Same-Mac replay alone is not accepted as live-near-end evidence. |
| M060 | Realtime near-end input-level diagnosis | Configure and launch `BACKEND=realtime`, click **Arm hands-free audio** once, use the built-in microphone/speaker without headphones, and run `python -m src.evals.realtime_input_diagnosis live`. Remain quiet for the baseline, speak one normal sentence when prompted with no answer playing, then speak once more while the counting answer is audible. | The command saves bounded normalized RMS/peak summaries for silence, `no_remote_playback`, and `remote_playback`, correlates each speech phase with server VAD, cleans up to `wake_owned`, and returns `capture_path`, `server_vad_sensitivity`, `full_duplex_attenuation`, `event_orchestration`, or `inconclusive`. It does not retain audio/transcripts, change Realtime settings, or claim RT003 passed. |

| M062 | RT001 automatic wake-to-connected handoff eval | With explicit microphone/OpenAI/cost authorization, configure and launch `BACKEND=realtime`, click **Arm hands-free audio** once, ensure the private `wake` fixture exists, and run `python -m src.evals.realtime_handoff live`. Do not speak; the saved fixture performs the only wake input. | The command automatically proves `wake_microphone_closed` precedes browser microphone request/acquisition and `host_connected` for one fresh session while the wake microphone remains closed, then explicitly stops and proves `host_stopped` precedes `wake_microphone_reopened` and final `wake_owned`. Missing, stale, wrong-session, duplicated, misordered, timeout, stop, or cleanup evidence exits non-zero with bounded sanitized FAIL evidence. No user question or assistant answer is part of RT001. |
| M063 | RT002 automatic two-turn fixture replay | Record private `turn-1` and `turn-2` fixtures once. For later authorized runs, launch and arm the Realtime host once, then run `python -m src.evals.realtime_two_turn live` without speaking. | Fixture integrity matches the local manifest; wake replays acoustically, then both saved turns inject after browser AEC through the active WebRTC data channel as two atomic audio conversation items; exactly one connection identity contains two ordered submissions and two `completed` responses; explicit cleanup restores `wake_owned`. The eval proves continuity, not transcript or answer semantics, and stores no fixture audio or content in evidence. |
| M064 | RT004 automatic close and next-wake recovery eval | With fresh explicit microphone/OpenAI/cost authorization, launch and Arm the Realtime host once, ensure the private `wake` fixture exists, and run `python -m src.evals.realtime_close_recovery live` without speaking. | The command automatically connects session A, explicitly stops, proves `host_stopped` precedes `wake_microphone_reopened`, replays the same wake without another Arm action, connects a distinct session B, and repeats bounded cleanup to final `wake_owned`. Missing, stale, reused, misordered, timeout, concurrent-ownership, or cleanup evidence exits non-zero with sanitized FAIL evidence. |

For M057, `/api/report` is the default evidence source. It is capped at 200
sanitized events and omits transcript, audio, credentials, tool arguments and
tool results. `REALTIME_DEBUG=1` remains bounded and is only for local diagnosis;
review its output before sharing. Realtime sessions incur API audio and optional
transcription charges. Packaging, signing, notarization, and launch-at-login are
not part of this MVP acceptance.

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

# F037 Real VAD Tuning Results

Date: 2026-07-10

## Test progression

### ARMED VAD enabled with initial defaults

With WebRTC VAD enabled, normal speech succeeded, but a hand clap was classified as voice (`vad_ratio=1.000`, `vad_ok=true`) and incorrectly triggered recording. The empty-transcript gate prevented an answer, but recording and transcription were still unnecessarily invoked.

### Stricter sustained-voice gate

The following tuning rejected two clap tests without entering recording:

```dotenv
VAD_BACKEND=webrtc
VAD_MODE=3
ARMED_VAD_REQUIRED_RATIO=0.75
ARMED_VAD_MIN_FRAMES=3
ARMED_VOICE_WINDOW_SECONDS=0.30
ARMED_VOICE_REQUIRED_RATIO=0.75
```

Both clap runs still contained WebRTC false-positive evidence (`max_vad_ratio=1.000`, with 5 and 9 VAD-voiced chunks), but neither satisfied the required rolling `3/4` sustained-voice window. A normally spoken `一加一等于几` did satisfy `3/4`, produced a complete transcript, and completed the answer loop.

### Paused short phrase and Recording VAD

With `RECORDING_VAD_ENABLED=1`, the phrase `一加一` followed by a 0.5–1 second pause and then `等于几` failed repeatedly. ARMED did not trigger on the short prefix and triggered only at 3.12–3.60 seconds on the suffix, after the 1.2 second pre-roll no longer contained `一加一`. Transcripts contained only `等于几` or a variant. Recording also wrote 100 chunks and stopped by `max_duration` in repeated runs instead of stopping on silence.

The recorder implementation treats any VAD ratio at or above `RECORDING_VAD_SPEECH_RATIO` as speech regardless of RMS. Because real WebRTC output can remain `1.000` for non-speech/quiet audio, supported 0–1 threshold tuning cannot reliably force endpointing while preserving the current comparison semantics.

### Working parameter workaround

The final local test configuration retained ARMED VAD, relaxed sustained speech to `2/3`, expanded pre-roll to cover the full ARMED interval, and disabled Recording VAD:

```dotenv
VAD_BACKEND=webrtc
VAD_MODE=3
ARMED_VOICE_WINDOW_SECONDS=0.24
ARMED_VOICE_REQUIRED_RATIO=0.66
ARMED_PRE_ROLL_SECONDS=4.00
ARMED_VAD_REQUIRED_RATIO=0.75
ARMED_VAD_MIN_FRAMES=3
RECORDING_VAD_ENABLED=0
```

Three final trials produced:

1. One failure before ARMED because the post-ACK boundary timed out with `post_ack_quiet_observed=false`, 19 suppressed chunks, 12 clipped chunks, and peak 32768. This is the separately known ACK boundary issue, not a VAD/pre-roll failure.
2. Success with `armed_trigger after=2.64s`, `pre_roll_ms=2640`, `stopped_by=silence`, and complete transcript `一加一等于几`.
3. Success with `armed_trigger after=0.96s`, `pre_roll_ms=960`, `stopped_by=silence`, and a complete arithmetic-question transcript.

## Assessment

- ARMED WebRTC VAD is usable with sustained-window tuning and can reject isolated clap noise despite individual WebRTC false positives.
- A 4-second ARMED pre-roll preserves short speech spoken before a pause when the trigger occurs on the later suffix.
- Recording VAD is not acceptable in the tested real environment and should remain disabled until endpointing logic and diagnostics are fixed.
- Post-ACK quiet-boundary failures remain an independent known issue.

Status: manual findings recorded; no product implementation change made.

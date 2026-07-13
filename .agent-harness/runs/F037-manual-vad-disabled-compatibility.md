# F037 Manual VAD-Disabled Compatibility Test

Date: 2026-07-10

Configuration context:

- `VAD_BACKEND=disabled`
- `RECORDING_VAD_ENABLED=0`
- wake acknowledgement and post-ACK guard enabled

Observed results:

1. Saying `1+1等于几` immediately after the acknowledgement failed twice. In the captured failure, `ACK_PLAYING` suppressed 13 chunks with `post_ack_max_rms=7434.5` and `post_ack_max_peak=18332`, preserved no chunks, then ARMED received only quiet audio and ended with `voiced_chunks=0` and `result=no_speech_timeout`.
2. Waiting approximately 1–2 seconds after the acknowledgement succeeded. That run suppressed 4 post-ACK chunks, ARMED triggered after 0.32 seconds, and transcription returned the complete `一加一等于几`.

Assessment:

- VAD was disabled in both runs (`max_vad_ratio=disabled`), so this is not caused by PR2 VAD classification.
- The timing evidence indicates that immediate user speech is still consumed while establishing the mandatory post-ACK quiet boundary.
- Delayed speech remains compatible and completes the full recording/transcription/answer path.

Status: known compatibility issue recorded for follow-up; no implementation or parameter change made in this test step.

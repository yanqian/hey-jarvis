# F048 Real-Device Acceptance

Date: 2026-07-15

## Environment and scope

- Source: user-run `tmp/debug.log` (kept untracked; summarized here without raw audio or credentials).
- Runtime: project Python 3.12 virtual environment with WebRTC VAD enabled.
- Scope: five normal continuous spoken questions, validating only post-speech Recording VAD endpointing.

## Results

All five recordings stopped naturally; none reached maximum duration:

| Trial | Duration | Chunks | Stop reason | Low-energy/high-VAD chunks |
| --- | ---: | ---: | --- | ---: |
| 1 | 4.40s | 55 | silence | 5 |
| 2 | 4.80s | 60 | silence | 7 |
| 3 | 4.40s | 55 | silence | 5 |
| 4 | 4.88s | 61 | silence | 4 |
| 5 | 5.36s | 67 | silence | 4 |

The nonzero disagreement counts confirm the real WebRTC backend continued to report voice on some low-energy chunks. F048's asymmetric RMS/VAD endpoint nevertheless completed the silence window in every trial, directly exercising the defect fixed by this feature. Transcription preserved each spoken question.

## Acceptance boundary

- Result: 5/5 normal continuous questions logged `stopped_by=silence`; 0/5 logged `max_duration`.
- The F048 real-device endpoint gate passes for the tested microphone and environment.
- Default configuration remains unchanged (`RECORDING_VAD_ENABLED=0`); enabling it by default is a separate product decision.
- Paused-prefix preservation, clap/transient rejection, Chinese calculator parsing beyond the F044 boundary, and post-playback microphone overflow are separate concerns.

# F043 Fast Coding Evidence

FAST_CODING_EVIDENCE: F043
CODING_PASS: F043

## Trigger

Real-device `tmp/debug.log` showed that speech started during or exactly at the end of the configured acknowledgement (`嗯` in the user's local `.env`) was consumed by the 18-chunk ACK playback drain. ARMED then timed out or started from a short tail, while waiting about one second remained stable. The log also exposed a synchronized `armed_trigger` with `noise_floor_has_samples=false`.

## Implementation

- Replaced the boolean ACK drain handoff with a structured result containing bounded preserved playback-tail chunks, safe low-energy noise seeds, drain counts, and completion-overlap quarantine.
- Omitted overflowed chunks, prevented clipped chunks from becoming noise evidence, and retained the existing conservative fallback for unsafe synchronization.
- Required useful noise samples for guarded synchronized ARMED baseline readiness.
- Kept playback-time chunks out of the voiced window so ACK echo cannot trigger recording by itself; valid post-playback speech triggers and receives the buffered tail as recording pre-roll.
- Added conservative exact configured acknowledgement-prefix cleanup after STT only when useful text remains.
- Real retesting showed OpenAI STT consistently rendered the configured `嗯` residue as ASCII `n` before Chinese question text. Added a narrow phonetic cleanup for exactly one leading `n`/`N` followed by a CJK character when the configured acknowledgement is `嗯`; ordinary English text is unchanged.
- Documented the no-AEC boundary: speech may begin during ACK playback but must continue after playback completion.

## Verification

- `.venv/bin/python -m unittest tests.test_state_machine`: 48 passed.
- `.venv/bin/python -m unittest discover -s tests`: 209 passed.
- `.venv/bin/python -m src.main --dry-run`: passed.
- `.venv/bin/python -m src.main --fake-backend`: passed.
- `git diff --check`: passed.

No live microphone, speaker, OpenAI, or network was used during automated verification. Real-device cases are documented in `MANUAL_TESTING.md` and remain the final external acceptance surface.

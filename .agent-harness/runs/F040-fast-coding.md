# F040 Fast Coding Evidence

Date: 2026-07-13

The repository orchestrator-first command `make -C .agent-harness work-fast` was attempted first and failed before coding handoff because the configured Codex Evaluator Agent runtime check exited unsuccessfully. Interactive provider-native coding fallback implemented only F040.

Implemented behavior:

- `MacOSPlayer.start()` starts `afplay` through an observable process-backed playback handle with `poll()` and error-checking `wait()` semantics.
- Existing synchronous `MacOSPlayer.play()` behavior remains unchanged for answer playback.
- ACK playback uses the observable handle when available and continuously reads/discards microphone chunks while playback remains active.
- The chunk whose blocking read can overlap playback completion is discarded by construction.
- Drain diagnostics include chunk, overflow, clipped, maximum RMS/peak, and completion fields without raw audio.
- Players without the new optional start boundary retain a logged synchronous compatibility fallback for fake and legacy paths.
- Player/state-machine tests cover successful and failed process handles, multiple drained chunks, overflow/clipping metrics, one deterministic wait, and proof that the next read is current post-playback audio.
- README and manual testing document the F040 boundary and explicitly defer immediate-speech handoff changes to F041.

Verification:

- `python3 -m unittest tests.test_player tests.test_state_machine`: 44 tests passed.
- Final root `./init.sh`: harness checks passed, 196 project tests passed, dry-run passed, and fake-backend smoke passed.

FAST_CODING_EVIDENCE: F040
CODING_PASS: F040

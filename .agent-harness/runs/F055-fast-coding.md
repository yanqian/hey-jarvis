# F055 Fast Coding Evidence

FAST_CODING_EVIDENCE: F055
CODING_PASS: F055

## Scope implemented

- Consumes completed Realtime input-transcription events as asynchronous, item-correlated control metadata.
- Normalizes configured short end phrases conservatively across Unicode form, case, outer punctuation, and ASR whitespace while retaining whole-utterance equality.
- Reuses the existing idempotent closing path and immediately stops browser media when the host reports an end-phrase match.
- Treats partial, missing, oversized, duplicated, failed, stale, reordered, and ordinary cancellation-language events safely without transcript logging.
- Leases the coordinator to one armed browser host identity so stale Chrome app windows cannot consume commands or inject events.
- Documents the optional transcription control, independent exit paths, rough-guide limitation, and separate ASR billing semantics.

## Coding verification

- Focused Realtime/config/documentation suite: 30 tests passed before live acceptance.
- Added a regression for ASR-inserted whitespace such as `good bye` and `结束 对话`; focused host suite: 10 tests passed.
- JavaScript syntax and `git diff --check` passed.
- No tracked pipeline defaults or private voice fixtures were changed.

## Live acceptance

See `F055-real-device-acceptance.md`. A real Chrome-hosted spoken end phrase produced the completed transcription control event, exact match, media teardown, and fresh wake-microphone recovery without transcript text in the report.

This file is Coding Agent evidence only. It does not contain evaluator approval and does not mark F055 done.

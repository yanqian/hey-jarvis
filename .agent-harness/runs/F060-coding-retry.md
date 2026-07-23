# F060 Coding Retry - Safe Negotiation Failure Diagnosis

FAST_CODING_EVIDENCE: F060

CODING_PASS: F060

## Summary

The user asked to continue F060 by identifying the repeated OpenAI WebRTC HTTP
429 without storing unsafe provider content. The browser now extracts only:

- HTTP status;
- OpenAI `error.type` and `error.code`;
- `x-request-id`;
- `retry-after`;
- available rate-limit remaining/reset headers.

The Python coordinator independently validates the status, field names, string
format, and length before retaining the existing bounded report event. The F060
evidence sanitizer applies the same allowlist. Full provider response bodies,
SDP, authorization headers, ephemeral secrets, API keys, audio, transcripts,
utterance text, and arbitrary fields are excluded.

## Verification

- Focused host, diagnosis, F059 regression, and documentation tests pass 42
  tests.
- `./init.sh` passes harness verification, 292 project tests, dry-run,
  fake-backend, and Realtime fake smoke.
- `git diff --check` passes.

## Authorized Live Result

After the user armed the Chrome host, one authorized live F060 start reproduced
the failure and saved bounded evidence:

```text
httpStatus=429
errorType=insufficient_quota
errorCode=insufficient_quota
failureStage=session_start
```

OpenAI did not expose an allowlisted request ID, retry-after, or rate-limit
remaining/reset header to this browser response. No full response body was
retained. The failure occurred before `host_connected` and before either human
speech prompt, so no test utterance was sent. Cleanup restored `wake_owned` with
the wake microphone open.

This identifies an account, organization, or project quota/credit/hard-limit
condition rather than a request-rate burst. F060 remains unfinished because its
required connected silence/no-playback/remote-playback diagnostic and separate
Evaluator approval cannot occur until API traffic is restored.

## Evaluator Result

Pending a separate cold-start Evaluator Agent. This coding record contains no
evaluator verdict and does not mark F060 done.

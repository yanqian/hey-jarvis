# Run Record: F113 - target Mac safe sidecar shutdown

## Summary

- Date: 2026-08-05 14:46-14:47 (Asia/Singapore)
- Build: current-source Debug `.app`
- Result: PASS

## Trial

The Debug app was manually resumed and reached `WAKE LISTENING`. Process
inspection identified the Python 3.12 development sidecar as PID 78972. Opening
Settings then exercised the existing `open_settings` shutdown path, which is a
valid genuine-shutdown trigger for F113 even though F114 will remove that stop
from ordinary Settings entry.

The lifecycle evidence was ordered and bounded:

```text
1785912413126 python health_check state=wake_listening
1785912413863 python shutdown_requested state=stopping
1785912414269 python process_stopped state=non_listening
1785912414366 native sidecar_stopped state=non_listening
```

After the trial, no product Python process remained. The complete pre-trial
DiagnosticReports baseline contained six `Python-*.ips` reports and ended at
`Python-2026-08-05-121108.ips`. The post-trial list was identical: no new report
with the previously reproduced PortAudio `OpenAndSetupOneAudioUnit` signature
was generated, and no Python-exit system dialog appeared.

No audio, transcript, answer, credential, SDP, ICE, provider body, or other
conversation content was retained in this evidence.

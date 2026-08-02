# Trusted trial evidence

F093 accepts at least three explicitly trusted Apple Silicon testers or clean
local user/device profiles. Put one privacy-safe JSON record per completed run
under `feedback/trusted-trials/`, using `trial-template.json` as the shape.

Do not record names, email addresses, serial numbers, API keys, audio,
transcripts, conversation text, screenshots containing secrets, or support
bundles. Use opaque IDs such as `trusted-tester-02`. Keep qualitative feedback
to product behavior and friction.

Every run must cover install, first run, wake, conversation, interruption,
cleanup, and relaunch. `fail` or `blocked` is valid evidence but creates a
release blocker that must become follow-up work rather than being averaged
away. Check the current gate with:

```bash
python3 scripts/verify_portfolio_completion.py
```

Use `--require-complete` only for the final F093 gate. Even when the result is
`GO_INTERNAL`, public binary distribution remains `HOLD`.

After recording the demo, copy `demo-evidence-template.json` to
`demo-evidence.json`, replace its reference, and truthfully update every field.
The completion gate rejects a missing/out-of-range demo, hidden checklist gaps,
sensitive material, or any public link to the unsigned binary.

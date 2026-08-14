# Trusted trial evidence

F093's current portfolio baseline uses the owner-led Apple Silicon trial already
recorded in this directory. The English and Chinese feature demos are published,
and the English and Chinese user guides are part of the deliverable. Additional
explicitly trusted Apple Silicon testers or clean local user/device profiles are
optional follow-up evidence. Put one
privacy-safe JSON record per completed run
under `feedback/trusted-trials/`, using `trial-template.json` as the shape.

Do not record names, email addresses, serial numbers, API keys, audio,
transcripts, conversation text, screenshots containing secrets, or support
bundles. Use opaque IDs such as `trusted-tester-02`. Keep qualitative feedback
to product behavior and friction.

Every recorded run should cover install, first run, wake, conversation, interruption,
cleanup, and relaunch. `fail` or `blocked` is valid evidence but creates a
release blocker that must become follow-up work rather than being averaged
away. Check the current gate with:

```bash
python3 scripts/verify_portfolio_completion.py
```

Use `--require-complete` only for the final F093 gate. The unsigned DMG may be
linked from the public GitHub Release for internal evaluation, but publicly trusted binary distribution remains blocked.

After recording the demo, copy `demo-evidence-template.json` to
`demo-evidence.json`, replace its reference, and truthfully update every field.
The completion gate rejects a missing/out-of-range demo, hidden checklist gaps,
sensitive material, or any public link to the unsigned binary.

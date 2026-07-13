# F037 WebRTC VAD Runtime Dependency Gap

Date: 2026-07-10

## Observed failure

With `VAD_BACKEND=webrtc`, starting the real assistant failed before wake-word preparation:

```text
ModuleNotFoundError: No module named 'pkg_resources'
src.vad.VadError: VAD_BACKEND=webrtc requires the optional webrtcvad package
```

`python -m pip install webrtcvad` reported that `webrtcvad 2.0.10` was already installed. The project diagnostic also incorrectly reported:

```text
[OK] dependency:webrtcvad: webrtcvad is importable
```

## Root cause

- `webrtcvad 2.0.10` imports `pkg_resources` at runtime.
- The virtual environment did not contain setuptools.
- Installing current `setuptools 83.0.0` still did not provide `pkg_resources`.
- Installing `setuptools<81` resolved the runtime import; the verified environment used `setuptools 80.10.2`.
- The current diagnostic uses module discovery rather than importing/constructing the configured VAD implementation, so it can report OK even though real startup fails.

## Temporary local workaround

```bash
python -m pip install "setuptools<81"
```

After applying the workaround, importing `pkg_resources` and `webrtcvad` and constructing `WebRtcVadDetector(mode=2)` succeeded with `vad_enabled=True`.

## Follow-up needed

Make the optional WebRTC VAD installation recoverable on supported Python versions by documenting or declaring its complete compatible dependency set, and change diagnostics to detect actual import/construction failures with an actionable message. No product implementation was changed while recording this issue.

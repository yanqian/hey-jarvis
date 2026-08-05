# Run Record: F120 - work-fast coding handoff

## Summary

- Date: 20260805T164447Z
- Agent role: Orchestrator fast handoff
- Feature: F120
- Result: in_progress

## Repository State

- Starting commit: 5a99c1a
- Ending commit: 5a99c1a
- Working tree status: M feature_list.json
 M progress.md
 M ../app/sidecar/product_sidecar.py
 M ../app/sidecar/tests/test_product_sidecar.py
 M ../app/src-tauri/tauri.conf.json
 M ../tests/test_macos_sidecar_packaging.py
?? runs/20260805T162919Z-F119-work-fast-handoff.md
?? runs/20260805T164338Z-F119-evaluation-pass.md
?? runs/F119-fast-coding.md
?? ../assets/realtime_acknowledgement_alloy_en.json
?? ../assets/realtime_acknowledgement_alloy_en.wav
?? ../assets/realtime_farewell_alloy_en.json
?? ../assets/realtime_farewell_alloy_en.wav
?? ../src/english_voice_cues.py
?? ../src/evals/english_voice_cues.py
?? ../tests/test_english_voice_cues.py
?? ../tmp/debug.log
?? ../tmp/pr1-real.log
?? ../tmp/realtime-english-cue-candidates/
?? ../tmp/realtime-evals/
?? ../tmp/realtime-farewell-candidates/

## Commands Run

```bash
python3 orchestrator.py --work-fast
```

## Evidence

- Fast handoff: FAST_CODING_HANDOFF: F120
- Coding evidence required: write a separate run record containing the fast coding evidence marker and matching coding pass verdict after implementation.
- Evaluator pass prohibited in coding evidence: do not write evaluator pass evidence during the fast coding phase.

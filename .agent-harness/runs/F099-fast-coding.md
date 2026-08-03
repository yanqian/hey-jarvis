# F099 fast coding evidence

FAST_CODING_EVIDENCE: F099

## Root-cause evidence

- Reproduced the reported real Debug path before coding: assistant gear restored `tauri://localhost?settings-request=1#settings-return` with the visible `Returning to Jarvis` container.
- Source inspection proved the assistant gear uses `window.history.back()` while F098 only made native menu/tray Settings URLs unique. The restored BFCache document retained Done's mutated container visibility; `pageshow` refreshed data but never reset the surface.
- A timed Done run began at `1785738406921`; native diagnostics did not record `sidecar_starting` until `1785738487679`, about 80.8 seconds later. Once native startup began, `sidecar_ready` arrived at `1785738490168`, about 2.49 seconds later. This distinguishes the throttled pre-start paint gate from actual sidecar readiness.

## Coding evidence

- Done no longer awaits `requestAnimationFrame` before restart. It records an allowlisted `runtime_restart_requested` event and immediately invokes restart.
- Native `restart_sidecar` now uses `tauri::async_runtime::spawn_blocking` with AppHandle state lookup, keeping blocking process readiness work off the Tauri UI/IPC path.
- `resetSettingsSurface()` synchronously hides the returning view and shows Settings on Settings load/show and before BFCache storage on pagehide.
- The Settings-only two-frame commit guard remains in place; the unsafe rAF gate was removed only from Done.
- The loopback assistant receives no new privileged Tauri IPC access.
- Focused documentation/source contracts, JavaScript syntax, Rust formatting, and all 17 Rust tests pass.

## Real-cycle correction

- The first rebuilt real cycle initially rendered Settings correctly, then blanked after sidecar shutdown. This proved that making BFCache state idempotent does not remove the underlying `history.back()` commit race from F096.
- The implementation therefore no longer retains history navigation. An intermediate probe passed a unique Settings return URL through the validated loopback control URL without adding remote native IPC.
- The first query-transport probe reached the loopback error state because `_handle_capability_bootstrap` issues `303 Location: /`, deliberately stripping the lease and every other query parameter after setting its cookie. The transport now uses a client-only fragment so the return URL is not sent to the server or logged and remains available to the page after bootstrap redirect.
- A subsequent real cycle proved that replacing F096's Settings-only double-frame commit guard with a 100 ms fallback can briefly render Settings and then blank after sidecar shutdown. The fallback was removed. Done remains rAF-free, while Settings entry retains the proven two-frame commit ordering before `enter_settings`.
- A later real cycle proved that even fragment-preserved HTTP-to-Tauri document navigation can briefly render Settings and then blank after sidecar shutdown. The final bridge is therefore the exact data-free `hey-jarvis://settings/open` intent. Tauri's navigation hook cancels it and schedules the already-proven native `open_settings_window()` helper. No remote native IPC or asynchronous sidecar protocol writer is introduced.

## Final real-App verification

- Three consecutive assistant → Settings → Done cycles used native Settings request tokens `1`, `2`, and `3`. Every entry rendered the Settings surface, including repeated accessibility reads of the first cycle, and every Done returned to the Ready assistant surface; no cycle restored Returning-to-Jarvis content or blanked.
- Native lifecycle timings for the three final cycles were:
  - request `1785740124758` → start `1785740124776`: 18 ms; start → ready: 1,846 ms.
  - request `1785740163326` → start `1785740163338`: 12 ms; start → ready: 1,794 ms.
  - request `1785740350210` → start `1785740350234`: 24 ms; start → ready: 1,715 ms.
- These measurements show that the artificial pre-start pause is gone. The remaining roughly 1.7–1.8 seconds is the observed local sidecar/model readiness interval, after native startup has already begun.

CODING_PASS: F099

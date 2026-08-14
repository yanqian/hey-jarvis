# Mac App Startup Performance

Hey Jarvis records a bounded local `hey-jarvis-startup-v1` timeline in
`Application Support/com.heyjarvis.desktop/diagnostics/startup*.jsonl*`.
It never sends startup telemetry over the network.

The three user-facing boundaries are deliberately separate:

- `native.window_shown`: macOS was asked to show the main window.
- `webview.home_interactive`: useful Home content has painted and its local UI
  initialization has completed.
- `native.voice_ready`: the separate voice runtime has confirmed wake listening.

Rust receipt time is the only cross-process timeline. `process_elapsed_ms` is
useful for work inside one WebView or sidecar process, but must not be subtracted
from another process's clock. Sidecar and WebView events received through native
IPC therefore include both source-process elapsed time and native receipt time.

## Repeatable sampling

Use the same built artifact, Mac, login state, preferences, and launch command
for every comparison. Do not arm the microphone or start a Realtime conversation.

1. Build the Debug or Release app once; do not rebuild between trials.
2. For a warm series, launch with `HEY_JARVIS_STARTUP_SAMPLE_KIND=warm`, wait for
   Home to settle, quit normally, and repeat at least five times.
3. For a cold series, quit normally, wait for the sidecar to exit, remove only
   operating-system file cache effects using the same documented lab procedure,
   then launch with `HEY_JARVIS_STARTUP_SAMPLE_KIND=cold`. Never delete user
   preferences, Keychain data, or diagnostics to simulate a cold launch.
4. Keep raw JSONL evidence and summarize each compatible series separately:

   ```bash
   python3 scripts/startup_report.py \
     "$HOME/Library/Application Support/com.heyjarvis.desktop/diagnostics" \
     --profile release --sample-kind warm --latest 5
   ```

The report rejects malformed records, duplicate milestones, and mixed build or
sample definitions. Compare medians first and report p90 and voice-ready effects;
never select one favorable run as performance evidence.

## F129 critical-path result

The F128 Release baseline showed that `window_shown` was gated by synchronous
Keychain reads and sidecar startup inside Tauri `setup`: five warm launches had
a 1,446 ms median and 13,209 ms p90 to window show, while the local shell had a
1,662 ms median and 13,499 ms p90. Once allowed to run, WebView paint itself
took only about 0.1–0.3 seconds, so WebView or wake-model work was not the
measured optimization target.

F129 shows the truthful local preparing shell first and performs credential and
voice-runtime startup in the background. Six compatible final Release warm
launches measured:

| Boundary | Before median / p90 | After median / p90 | Median change |
| --- | ---: | ---: | ---: |
| Window shown | 1,446 / 13,209 ms | 167.5 / 189 ms | 88.4% faster |
| Local shell interactive | 1,662 / 13,499 ms | 367.5 / 430 ms | 77.9% faster |

The final unsigned development bundle did not complete Keychain authorization
in these six after-samples, so no after `sidecar_ready` or `voice_ready` value is
claimed. One retained long sample confirmed that the preparing shell stays
responsive, exposes Settings without starting a second Keychain read, and
changes to a truthful slow-start notice after 30 seconds. Fake-sidecar and Rust
supervisor tests continue to verify the later ready transition without network,
credentials, microphone, or paid API use.

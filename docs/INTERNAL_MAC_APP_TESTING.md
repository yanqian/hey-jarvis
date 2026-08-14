# Unsigned internal Mac app testing

Hey Jarvis `0.1.0` is available as an Apple Silicon, macOS 14+ **internal test
build**. Its GitHub Release asset is publicly downloadable, but the build has
no Apple Developer ID distribution signature and is not notarized. Treat it as
an internal evaluation build, not a general consumer release.

An ad-hoc signature may be present because macOS tooling uses it to seal local
code. It provides no developer identity, notarization, or public distribution
trust. `INTERNAL-UNSIGNED` always means “no Apple distribution trust.”

## Build and verify

On an Apple Silicon Mac with Python 3.12, Node/npm, Rust, Tauri's prerequisites,
and network access for pinned build dependencies:

```bash
./scripts/build_internal_macos_release.sh
```

The command rebuilds the pinned Python sidecar, creates the Tauri `.app`, then
writes these files under `build/internal-release/`:

- `Hey-Jarvis-0.1.0-INTERNAL-UNSIGNED-arm64.dmg`
- the matching `.sha256`
- the matching `.manifest.json`

It mounts the DMG and fails unless bundle identity/version, macOS 14 minimum,
microphone text, arm64 nested code, packaged resources, size, checksum, and
the absence of credential-shaped data and developer checkout paths all pass.
The manifest states that Developer ID signing, notarization, stapling,
Gatekeeper readiness, and public distribution are all false. Rebuilding an
existing version retains the prior DMG and metadata under a SHA-256-named
`rollback/` directory.

Before installing, compare the received file to the owner's checksum:

```bash
shasum -a 256 Hey-Jarvis-0.1.0-INTERNAL-UNSIGNED-arm64.dmg
```

## Trusted tester installation

1. Confirm the checksum with the owner and open the DMG.
2. Read `INTERNAL-UNSIGNED.txt`, then drag **Hey Jarvis** to Applications.
3. Open it from Applications. If macOS blocks it, stop and review the source.
   Do not disable Gatekeeper and do not run an `xattr` command. Open **System
   Settings → Privacy & Security**,
   review the warning, and choose **Open Anyway** only if you trust the owner.
4. Enter your own OpenAI API key. The optional Finnhub key enables stock
   quotes. Keys stay in macOS Keychain and are not shown again.
5. Read the privacy/API-cost disclosure, grant microphone access to **Hey
   Jarvis**, and select **Check microphone & start**.
6. Select **Enable voice assistant**, say “Hey Jarvis,” complete one short
   conversation, try a follow-up and “再见,” then verify wake listening returns.
7. Open or focus the same dedicated Settings window from the conversation-window
   gear, the menu-bar **Settings…** item, and `⌘,`. Confirm wake listening and
   the sidecar stay active while inspecting General, API
   Keys, Microphone, Privacy & Diagnostics, and About. Confirm the action always
   reads **Apply & Done**. With no runtime-affecting change it closes only
   Settings. An explicit microphone check should safely pause previously active
   voice; applying must restore real wake listening before Settings closes. If
   voice was inactive on entry, the same action must close without starting it.
8. In Privacy & Diagnostics, use **Export support bundle** if reporting a
   problem. The bundle excludes keys, raw audio, and transcripts. Quit from
   the tray and confirm listening and the sidecar stop; relaunch once.

**Clear diagnostics** deletes the diagnostic history present at that moment;
it does not disable diagnostics or delete previously exported support bundles.
The running app may immediately create a new lifecycle log, including the
subsequent quit and relaunch events.

OpenAI Realtime usage is paid against the key owner's account. Project budgets
and rate limits are monitoring controls, not a guaranteed hard spending cap.
Pre-wake audio stays in the local wake detector; conversation audio reaches
OpenAI after wake and stops at session end.

## Feedback, known limits, and recovery

Report macOS version, Mac model, build version/checksum, install friction,
microphone/setup result, wake/answer/follow-up/interruption/end behavior,
support-export result, quit/relaunch result, and any visible error. Never send
API keys, raw recordings, or transcript content.

Known limits: Apple Silicon and macOS 14+ only; no Developer ID/notarization;
manual install/update/rollback; no automatic update; no launch at login; BYOK;
and direct trusted-source distribution only.

To update, quit Hey Jarvis, retain the current DMG, install the newer version
from its independently verified DMG, and run the short acceptance flow again.
To roll back, quit, move the installed app to Trash, install the retained prior
DMG, and relaunch. The stable bundle identifier preserves the same Application
Support and Keychain namespace; never run two versions simultaneously.

To uninstall, quit the tray app and move `/Applications/Hey Jarvis.app` to
Trash. Optionally remove its keys using the app's Settings before uninstalling.
Application Support data at
`~/Library/Application Support/com.heyjarvis.desktop` may be removed manually
only if logs and onboarding state are no longer needed.

Publicly trusted binary distribution remains blocked until a separately planned
Developer ID signing and notarization feature passes clean Gatekeeper testing.

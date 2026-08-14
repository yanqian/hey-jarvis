# Hey Jarvis User Guide

Hey Jarvis is a local-first voice assistant for Apple Silicon Macs. It listens
locally for “Hey Jarvis” and sends conversation audio to OpenAI only after the
assistant is awakened. The app uses BYOK (Bring Your Own Key): your OpenAI API
Key is stored by macOS Keychain.

> Version `0.1.0 INTERNAL-UNSIGNED` is publicly downloadable for internal
> evaluation. It is not Developer ID signed or notarized and is not a general
> consumer release.

## Before you start

- An Apple Silicon Mac (M-series)
- macOS 14 or later
- Your own OpenAI API Key
- Internet access and a working microphone
- OpenAI API usage is billable to the account that owns the key

The app does not embed a shared key or place your key in the web page, command
line arguments, logs, recordings, transcripts, or support bundles.

## Install the app

1. Obtain `Hey-Jarvis-0.1.0-INTERNAL-UNSIGNED-arm64.dmg` and its SHA-256 value
   directly from the project owner.
2. Verify the file before opening it:

   ```bash
   shasum -a 256 Hey-Jarvis-0.1.0-INTERNAL-UNSIGNED-arm64.dmg
   ```

   Continue only when the result matches the value supplied by the owner.
3. Open the DMG, read `INTERNAL-UNSIGNED.txt`, and drag **Hey Jarvis** to
   **Applications**.
4. Launch it from **Applications**. If macOS blocks the app, open
   **System Settings → Privacy & Security**, review the source, and choose
   **Open Anyway** only when you trust the owner. Do not disable Gatekeeper or
   run an `xattr` command to bypass quarantine.

## First-run setup

1. Open **Settings → API Keys** and enter your own OpenAI API Key. Optionally
   add a Finnhub Key for stock quotes. After saving, the app shows only whether
   a key is configured.
2. Read the privacy and API-cost disclosure.
3. In **System Settings → Privacy & Security → Microphone**, allow
   **Hey Jarvis** to use the microphone.
4. Return to the app and choose **Check microphone & start**.
5. When the Realtime page starts for the first time, choose
   **Enable voice assistant**.

If the microphone check fails, close other apps that may own the microphone and
run the check again. Replacing or deleting a key safely pauses the current
runtime and exposes a recovery action; do not continue testing the old session.

## Daily use

When the app shows **Wake listening**:

1. Say “Hey Jarvis”.
2. Wait for the acknowledgement, then ask your question.
3. Ask follow-up questions in the same Realtime session without repeating the
   wake phrase.
4. Interrupt a long answer with a clearly different question when needed.
5. Say “再见” to end the session. The app releases WebView audio and restores
   local wake listening.

Examples include general questions, time, weather, exchange rates, arithmetic,
and stock quotes when Finnhub is configured. Smart Speaker Mode can preserve
wake behavior while the Mac is locked or the display is off; actual behavior
depends on macOS, power settings, the microphone, and the device.

## Settings, diagnostics, and quit

- Open Settings from the top-right button, the menu-bar icon, or `⌘,`.
- **Apply & Done** is the single Settings completion action. With no
  runtime-affecting change it simply closes Settings. After a setting safely
  pauses a ready or listening sidecar, it restores the prior state and closes
  only after recovery succeeds. It never quits the app or starts an assistant
  that was already inactive when Settings opened.
- Use **Privacy & Diagnostics → Export support bundle** to create a redacted
  support bundle. It excludes keys, raw audio, and transcripts.
- **Clear diagnostics** clears the current diagnostic history; it does not
  delete support bundles that were already exported.
- Quit from the menu bar and confirm that wake listening and the sidecar stop.
  Relaunch once when checking a new installation.

## Update, rollback, and uninstall

This internal build uses manual updates. Quit the app, retain the current DMG,
verify the new `INTERNAL-UNSIGNED` DMG, and install the replacement. If the new
version causes a problem, move it to the Trash and restore the retained DMG.
Never run two versions at the same time.

To uninstall, quit the menu-bar app and move `/Applications/Hey Jarvis.app` to
the Trash. If you no longer need local settings and logs, you may also remove:

```text
~/Library/Application Support/com.heyjarvis.desktop
```

Before doing so, confirm that the local state is no longer needed. Delete saved
credentials from the app's Settings before removing the app.

## What to include in a problem report

Include the macOS version, Mac architecture, app version, DMG checksum, steps
to reproduce, whether recovery succeeded, and a redacted support bundle. Never
send an API Key, recording, transcript, full name, email address, or serial
number.

For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md). For
the internal distribution boundary, see
[INTERNAL_MAC_APP_TESTING.md](INTERNAL_MAC_APP_TESTING.md). For the Chinese
version, see [USER_GUIDE_ZH.md](USER_GUIDE_ZH.md).

# Mac App architecture

This document defines the production ownership boundaries established by F087.
The implementation under `app/` is the product shell. The isolated
`spikes/tauri_realtime/` tree remains feasibility evidence and is not imported,
copied, or bundled by the product.

## Product boundary

Hey Jarvis is a local-first, three-part macOS application:

- Rust/Tauri owns app identity, the tray and window, single-instance behavior,
  Application Support paths, native secrets, permissions, and sidecar
  supervision.
- WKWebView owns Realtime microphone capture, WebRTC negotiation, remote audio,
  interruption signals, and media teardown. F087 contains only a status UI;
  Realtime integration belongs to F088.
- Python owns wake inference and reusable assistant behavior. F087 uses a
  protocol-only fake sidecar; accepted runtime behavior is integrated in F088
  and the distributable Python runtime is produced in F090.

The existing CLI remains independent. The app shell must not become a
prerequisite for running `python -m src.main`.

## App and sidecar protocol

The native process supervises exactly one sidecar over inherited stdin/stdout
using newline-delimited JSON. There is no fixed port or repository `.env`
contract.

Every message has four fields:

```json
{
  "protocol_version": 1,
  "sequence": 1,
  "session_id": "session-...",
  "payload": {"kind": "startup"}
}
```

Version 1 defines `startup`, `ready`, `settings`, `session`, `lifecycle`,
`error`, and `shutdown` payloads. Both peers reject:

- unknown versions, message kinds, or fields;
- messages larger than 32 KiB or containing NUL;
- zero, repeated, or decreasing sequence numbers;
- empty, malformed, oversized, or changed session identities;
- credential-shaped keys or values.

Secrets are deliberately outside this protocol in F087. F089 must define and
verify a separate native-to-sidecar launch secret channel before any real key
is supplied.

## Lifecycle

At app setup, Tauri resolves its macOS Application Support directory, creates a
random per-launch session identity, starts the fake Python sidecar with piped
stdin/stdout, sends `startup`, and requires `ready` within three seconds.
Health requests and lifecycle responses use the same validated session.

Tray Quit, normal app exit, restart, and supervisor destruction send a bounded
`shutdown`, close the parent pipe, wait no more than two seconds, and then kill
the child if necessary. The fake sidecar treats stdin EOF as parent loss and
exits, preventing an orphan process. Startup and protocol failures leave a
visible non-ready state rather than silently proceeding.

The first release targets Apple Silicon and macOS 14 or later. F087 does not
request microphone access, contact OpenAI, package Python, sign an app, or
produce a distributable bundle.

## Identity and release decisions

The provisional identity is:

- product name: `Hey Jarvis`
- bundle identifier: `com.heyjarvis.desktop`
- initial app version: `0.1.0`
- minimum macOS version: `14.0`

Before F092 signs the first friend release, freeze:

- the final bundle identifier and Apple Developer Team;
- the version and release-channel source of truth;
- final icons, microphone usage text, and hardened-runtime entitlements;
- Application Support and Keychain service/account names;
- Developer ID and notarization credential ownership;
- DMG name, download URL, retained rollback artifact, and checksum format.

Changing bundle identity after distribution can disrupt TCC microphone grants,
Keychain access, and update continuity, so it is a release-blocking decision.

## Verification

`./init.sh` validates the product/source isolation, frontend syntax, fake
sidecar protocol and parent-loss behavior, Rust protocol and supervision tests,
the existing Python suite, and the existing Realtime fake smoke. These checks
require no microphone, OpenAI credential, signing identity, or live service.

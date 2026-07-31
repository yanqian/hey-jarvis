# Mac App architecture

This document defines the production ownership boundaries established by F087
and the accepted-runtime integration implemented by F088.
The implementation under `app/` is the product shell. The isolated
`spikes/tauri_realtime/` tree remains feasibility evidence and is not imported,
copied, or bundled by the product.

## Product boundary

Hey Jarvis is a local-first, three-part macOS application:

- Rust/Tauri owns app identity, the tray and window, single-instance behavior,
  Application Support paths, native secrets, permissions, and sidecar
  supervision.
- WKWebView owns Realtime microphone capture, WebRTC negotiation, remote audio,
  interruption signals, and media teardown. The native bootstrap accepts only
  a product-sidecar URL on `127.0.0.1`, exchanges its one-time capability for
  an HttpOnly cookie, and then loads the existing accepted media surface.
- Python owns wake inference and reusable assistant behavior. The product
  sidecar composes the existing wake detector, Realtime controller, coordinator,
  six-tool router, language behavior, and privacy filters. The protocol-only
  fake remains a deterministic supervisor fixture. F090 produces the
  distributable Python executable.

The existing CLI remains independent. The app shell must not become a
prerequisite for running `python -m src.main`.

## App and sidecar protocol

The native process supervises exactly one sidecar over inherited stdin/stdout
using newline-delimited JSON. There is no fixed port or repository `.env`
contract.

Every message has four fields:

```json
{
  "protocol_version": 2,
  "sequence": 1,
  "session_id": "session-...",
  "payload": {"kind": "startup"}
}
```

Version 2 defines `startup`, `ready`, `settings`, `session`, `lifecycle`,
`error`, and `shutdown` payloads. Startup carries explicit Application Support
and bundle-resource directories. Ready may carry the loopback media URL; it
never carries credentials. Both peers reject:

- unknown versions, message kinds, or fields;
- messages larger than 32 KiB or containing NUL;
- zero, repeated, or decreasing sequence numbers;
- empty, malformed, oversized, or changed session identities;
- credential-shaped keys or values.

The OpenAI key never enters the protocol, loopback JSON settings, or JavaScript.
During F088 development the sidecar can inherit the key directly from its
controlled launch environment. F089 replaces that temporary developer path
with Keychain-backed native configuration and a bounded native-to-sidecar
launch channel.

## Lifecycle

At app setup, Tauri resolves its macOS Application Support and bundle resource
directories, creates a random per-launch session identity, starts the product
sidecar with piped stdin/stdout, sends `startup`, and requires `ready` within
30 seconds. This bounded window includes wake-model warmup and initial
microphone acquisition; a redacted sidecar error is surfaced directly instead
of being mislabeled as malformed readiness. Health requests and lifecycle
responses use the same validated session. The sidecar binds an ephemeral loopback port; requests are denied
until the native bootstrap URL exchanges its unguessable per-launch capability
for an HttpOnly, SameSite cookie.

Debug builds may launch `product_sidecar.py` through an explicitly configurable
Python interpreter so developers can work from source. Release builds do not
have this fallback: they launch `sidecar/hey-jarvis-sidecar` from the resolved
bundle resource directory and fail closed when it is absent. F090 owns creation
and bundling of that executable, so a friend release cannot depend on terminal
PATH, a repository checkout, or separately installed Python.

Tray Quit, normal app exit, restart, and supervisor destruction send a bounded
`shutdown`, close the parent pipe, wait no more than two seconds, and then kill
the child if necessary. The fake sidecar treats stdin EOF as parent loss and
exits, preventing an orphan process. Startup and protocol failures leave a
visible non-ready state rather than silently proceeding.

The first release targets Apple Silicon and macOS 14 or later. F088 integrates
the real runtime and WKWebView media path but does not package Python, persist a
key, sign an app, or produce a distributable bundle; those remain F089-F092.

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

`./init.sh` validates product/source isolation, the native loopback allowlist,
the product and fake sidecar protocols, parent-loss behavior, explicit resource
paths, release launch selection, Rust supervision, RT001-RT004, all six tools,
acknowledgement/input gating, the 60-second idle policy, cleanup/reacquisition,
and the existing CLI. These checks require no microphone, OpenAI credential,
signing identity, or live service.

F088 additionally requires one explicitly authorized Apple Silicon run using
built-in microphone and speakers. That run must cover wake, a normal and
follow-up turn, a tool turn, deliberate interruption, semantic ending, media
release, wake recovery, Quit, and relaunch. Offline tests cannot substitute for
this device evidence.

# F118 bilingual native visual acceptance

Date: 2026-08-05 (Asia/Singapore)

Artifact: `app/src-tauri/target/debug/bundle/macos/Hey Jarvis.app`, refreshed
with the executable from the successful current-source Debug build.

## English inspection

- General rendered the new Language group with exactly English and 简体中文.
- Settings, Done, Voice status, setup actions, Smart Speaker content, and the
  local-before-wake disclosure remained visible and correctly grouped at the
  ordinary/compact native window size.
- Fullscreen preserved the top controls, two-column layout, complete General
  content, focus, and readable status text without clipping or overflow.

## Simplified Chinese inspection

- Selecting 简体中文 immediately changed document content, navigation,
  accessibility text, dynamic readiness/status text, actions, and the success
  message without leaving or restarting the app.
- General, API 密钥, 麦克风, 隐私与诊断, and 关于 were each inspected through
  the native accessibility tree. All app-owned visible content was Chinese;
  stable brand and platform names such as Hey Jarvis, OpenAI, Finnhub, macOS,
  and Apple Silicon remained unchanged intentionally.
- Ordinary/compact and fullscreen screenshots showed intact hierarchy,
  wrapping, dividers, controls, and privacy copy with no mixed-language
  fallback or visible overflow.

No microphone, credentials, paid conversation, speaker, export, clear action,
or other runtime-affecting control was invoked. The preference was restored to
English after inspection.

VISUAL_ACCEPTANCE_PASS: F118

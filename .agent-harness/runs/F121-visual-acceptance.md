# F121 native visual acceptance

VISUAL_ACCEPTANCE_PASS: F121

The rebuilt macOS Debug app was inspected through its accessibility tree and
native screenshots after the owner unlocked the target Mac.

- English, 560x600: one `Language` heading, the combined timing sentence, and
  the `English` popup stack cleanly with no clipping or redundant label.
- English, full screen: copy and popup align in one row; the divider and next
  Settings group remain intact.
- Simplified Chinese, 560x600: one `语言` heading, the complete combined Chinese
  sentence, and the `简体中文` popup stack cleanly with no overflow.
- Simplified Chinese, full screen: localized copy and popup align in one row;
  no mixed-language fallback or displaced adjacent content was visible.
- Accessibility named the popup from the localized heading and exposed the
  localized merged sentence as its description in both languages.

No runtime action, microphone use, network call, credential access, speaker
playback, or paid API action occurred. The preference was restored to English,
full screen was exited, and the Debug app was closed after inspection.

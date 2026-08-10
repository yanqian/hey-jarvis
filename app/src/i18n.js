export const ENGLISH = "en";
export const SIMPLIFIED_CHINESE = "zh-CN";

export function supportedLocale(value) {
  return value === SIMPLIFIED_CHINESE ? SIMPLIFIED_CHINESE : ENGLISH;
}

export function text(locale, english, chinese) {
  return supportedLocale(locale) === SIMPLIFIED_CHINESE ? chinese : english;
}

const STATIC_ZH = new Map(Object.entries({
  Settings: "设置",
  "RESUME REQUIRED": "需要恢复",
  "Voice assistant paused": "语音助手已暂停",
  "The Mac slept, so microphone access was released safely.": "Mac 进入了睡眠，因此麦克风访问已被安全释放。",
  "Resume voice assistant": "恢复语音助手",
  "Wake listening is off until you resume.": "恢复前，唤醒监听保持关闭。",
  STARTING: "正在启动",
  "Returning to Jarvis": "正在返回 Jarvis",
  "Starting the local voice runtime…": "正在启动本地语音运行环境…",
  Done: "完成",
  "VOICE STATUS": "语音状态",
  Checking: "正在检查",
  "Reading local voice availability.": "正在读取本地语音可用状态。",
  General: "通用",
  "API Keys": "API 密钥",
  Microphone: "麦克风",
  "Privacy & Diagnostics": "隐私与诊断",
  About: "关于",
  GENERAL: "通用",
  "Voice assistant": "语音助手",
  "Hey Jarvis uses local wake detection and starts an OpenAI conversation only after the wake phrase.": "Hey Jarvis 使用本地唤醒检测，只有听到唤醒词后才会开始 OpenAI 对话。",
  Appearance: "外观",
  "Day mode uses a softer paper-white palette to reduce screen glare while recording.": "白天模式使用柔和的纸张白配色，减少录制时的屏幕反光。",
  Night: "夜间",
  Day: "白天",
  Language: "语言",
  "The interface updates immediately; fixed voice cues use the selected language from the next wake.": "界面会立即切换；固定语音提示从下一次唤醒起使用所选语言。",
  "Setup and start": "设置与启动",
  "Review the requirements for voice listening, then start or check them again.": "检查语音监听所需条件，然后启动或重新检查。",
  "Hey Jarvis is ready when you are": "准备好后即可启动 Hey Jarvis",
  "Checking local setup…": "正在检查本地设置…",
  "Check microphone & start": "检查麦克风并启动",
  "Run readiness check": "运行就绪检查",
  "Smart Speaker Mode": "智能音箱模式",
  "Control whether Hey Jarvis stays available during normal Mac idle time.": "控制 Hey Jarvis 是否在 Mac 正常闲置期间保持可用。",
  "Prevent automatic sleep while listening": "监听时防止系统自动睡眠",
  "Off. Hey Jarvis follows normal Mac sleep behavior.": "已关闭。Hey Jarvis 遵循 Mac 的正常睡眠行为。",
  "Enable Smart Speaker Mode": "启用智能音箱模式",
  "How sleep and wake work": "睡眠与唤醒如何工作",
  "When enabled, Hey Jarvis prevents automatic system sleep only while wake listening is genuinely active. The display may still turn off and the Mac may be locked. This can use more battery; explicit Sleep and closing a MacBook lid stop listening while asleep, then make one safe recovery attempt after wake. Shutdown still stops voice availability.": "启用后，Hey Jarvis 只会在唤醒监听真正处于活动状态时防止系统自动睡眠。显示器仍可关闭，Mac 也可锁定。这可能消耗更多电量；手动睡眠或合上 MacBook 会在睡眠期间停止监听，并在唤醒后进行一次安全恢复尝试。关机仍会停止语音功能。",
  "Local until you wake it.": "唤醒前始终在本地。",
  "Wake phrase detection stays on this Mac. Conversation audio reaches OpenAI only after wake.": "唤醒词检测始终留在这台 Mac 上。只有唤醒后，对话音频才会发送给 OpenAI。",
  "API KEYS": "API 密钥",
  "Private credentials": "私密凭据",
  "Keys are entered in a native secure prompt and stored in macOS Keychain. Their values never appear here.": "密钥通过原生安全窗口输入并存储在 macOS 钥匙串中，密钥内容不会显示在这里。",
  Required: "必需",
  "Checking macOS Keychain…": "正在检查 macOS 钥匙串…",
  "Add key": "添加密钥",
  Delete: "删除",
  Optional: "可选",
  "Used only for stock quotes.": "仅用于股票报价。",
  "Your API usage": "你的 API 用量",
  "You provide the OpenAI key and are responsible for its usage. OpenAI Project budgets and rate limits are monitoring controls, not a guaranteed hard spending cap.": "你需要提供 OpenAI 密钥并对其用量负责。OpenAI Project 预算和速率限制属于监控措施，并不保证形成严格的消费上限。",
  MICROPHONE: "麦克风",
  "Input permission": "输入权限",
  "Permission is requested only during an explicit check or while a voice conversation is active.": "仅在你主动检查或语音对话正在进行时请求权限。",
  "Microphone access": "麦克风访问",
  "Permission has not been checked yet.": "尚未检查权限。",
  "Check microphone": "检查麦克风",
  "Open System Settings": "打开系统设置",
  "Running a new microphone check safely pauses the voice runtime first. The temporary check stream is released immediately.": "重新检查麦克风时会先安全暂停语音运行环境，临时检查音频流会立即释放。",
  "PRIVACY & DIAGNOSTICS": "隐私与诊断",
  "Local support data": "本地支持数据",
  "Diagnostics contain bounded lifecycle events only—never keys, raw audio, transcripts, answers, tool arguments, SDP, ICE, or provider bodies.": "诊断仅包含有限的生命周期事件，绝不包含密钥、原始音频、转写、回答、工具参数、SDP、ICE 或服务提供方正文。",
  "Wake detection stays local.": "唤醒检测保留在本地。",
  "Credentials stay in Keychain.": "凭据保留在钥匙串中。",
  "No audio or transcripts in support exports.": "支持导出中不包含音频或转写。",
  "Quitting the tray app stops listening. Support exports remain on this Mac until you choose to share them.": "退出菜单栏应用会停止监听。支持导出会保留在这台 Mac 上，直到你选择分享。",
  "Export support bundle": "导出支持包",
  "Clear diagnostics": "清除诊断",
  ABOUT: "关于",
  "A local-first macOS voice assistant built as a personal AI engineering project.": "一款本地优先的 macOS 语音助手，也是个人 AI 工程项目。",
  Version: "版本",
  "0.1.0 internal beta": "0.1.0 内部测试版",
  Distribution: "分发方式",
  "Unsigned trusted testing only": "仅限可信环境的未签名测试",
  Platform: "平台",
  "Public binary distribution, accounts, billing, telemetry, and automatic updates are not part of this build.": "此版本不包含公开二进制分发、账户、计费、遥测或自动更新。",
}));

const ATTRIBUTE_ZH = new Map(Object.entries({
  "Settings sections": "设置分类",
}));

const originals = new WeakMap();

export function applyDocumentLocale(locale) {
  const resolved = supportedLocale(locale);
  document.documentElement.lang = resolved;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!originals.has(node)) originals.set(node, node.nodeValue);
    const original = originals.get(node);
    const trimmed = original.trim();
    if (!trimmed || !STATIC_ZH.has(trimmed)) {
      node.nodeValue = original;
      continue;
    }
    const leading = original.slice(0, original.indexOf(trimmed));
    const trailing = original.slice(original.indexOf(trimmed) + trimmed.length);
    node.nodeValue = resolved === SIMPLIFIED_CHINESE
      ? `${leading}${STATIC_ZH.get(trimmed)}${trailing}`
      : original;
  }
  for (const element of document.querySelectorAll("[aria-label], [title]")) {
    for (const attribute of ["aria-label", "title"]) {
      if (!element.hasAttribute(attribute)) continue;
      const storage = `i18n${attribute === "title" ? "Title" : "Aria"}`;
      if (!element.dataset[storage]) element.dataset[storage] = element.getAttribute(attribute);
      const original = element.dataset[storage];
      element.setAttribute(attribute, resolved === SIMPLIFIED_CHINESE && ATTRIBUTE_ZH.has(original)
        ? ATTRIBUTE_ZH.get(original)
        : original);
    }
  }
}

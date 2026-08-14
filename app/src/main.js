import { applyDocumentLocale, supportedLocale, text } from "./i18n.js";

const invoke = window.__TAURI__?.core?.invoke;
const startupNavigationElapsed = () => Math.max(0, Math.min(300000, Math.round(performance.now())));

function recordStartup(stage, elapsed = startupNavigationElapsed()) {
  if (!invoke) return Promise.resolve();
  return invoke("record_startup_milestone", {
    stage,
    processElapsedMs: elapsed,
  }).catch(() => {});
}

recordStartup("script_started");

const elements = {
  resumeView: document.querySelector("#resume-view"),
  resumeVoice: document.querySelector("#resume-voice"),
  resumeSettings: document.querySelector("#resume-settings"),
  resumeStatus: document.querySelector("#resume-status"),
  settingsShell: document.querySelector("#settings-shell"),
  returningView: document.querySelector("#returning-view"),
  returningStatus: document.querySelector("#returning-status"),
  returningSettings: document.querySelector("#returning-settings"),
  panels: [...document.querySelectorAll("[data-settings-panel]")],
  navItems: [...document.querySelectorAll("[data-panel]")],
  openaiStatus: document.querySelector("#openai-status"),
  finnhubStatus: document.querySelector("#finnhub-status"),
  microphoneStatus: document.querySelector("#microphone-status"),
  readiness: document.querySelector("#assistant-readiness"),
  message: document.querySelector("#setup-message"),
  saveOpenai: document.querySelector("#save-openai"),
  deleteOpenai: document.querySelector("#delete-openai"),
  saveFinnhub: document.querySelector("#save-finnhub"),
  deleteFinnhub: document.querySelector("#delete-finnhub"),
  start: document.querySelector("#start"),
  microphoneCheck: document.querySelector("#microphone-check"),
  microphoneSettings: document.querySelector("#microphone-settings"),
  readinessCheck: document.querySelector("#readiness-check"),
  smartSpeakerMode: document.querySelector("#smart-speaker-mode"),
  smartSpeakerStatus: document.querySelector("#smart-speaker-status"),
  returnAssistant: document.querySelector("#return-assistant"),
  voiceStatusLabel: document.querySelector("#voice-status-label"),
  voiceStatusDetail: document.querySelector("#voice-status-detail"),
  exportSupport: document.querySelector("#export-support"),
  clearDiagnostics: document.querySelector("#clear-diagnostics"),
  diagnosticsMessage: document.querySelector("#diagnostics-message"),
  appLanguage: document.querySelector("#app-language"),
  appTheme: document.querySelector("#app-theme"),
  wakeDiagnosticsEnabled: document.querySelector("#wake-diagnostics-enabled"),
  wakeDiagnosticsStatus: document.querySelector("#wake-diagnostics-status"),
  wakeThreshold: document.querySelector("#wake-threshold"),
  wakeConfirmationFrames: document.querySelector("#wake-confirmation-frames"),
  wakeTuningEffective: document.querySelector("#wake-tuning-effective"),
};

let setup = null;
let lastVoiceAvailability = null;
let runtimeRestartNeeded = false;
let settingsEntryAvailabilityCaptured = false;
let settingsEntryRuntimeIntent = "inactive";
let applyRetryNeeded = false;
let appLanguage = "en";
let appTheme = "night";
const SETTINGS_HASH = "#settings";
const RESUME_REQUIRED_HASH = "#resume-required";

const DYNAMIC_ZH = new Map(Object.entries({
  "That key format is invalid. Copy the complete key without spaces and try again.": "密钥格式无效。请复制不含空格的完整密钥后重试。",
  "Add an OpenAI API key before starting Hey Jarvis.": "启动 Hey Jarvis 前请先添加 OpenAI API 密钥。",
  "macOS denied Keychain access. Unlock your login keychain and try again.": "macOS 拒绝访问钥匙串。请解锁登录钥匙串后重试。",
  "Keychain is locked or interaction is unavailable. Unlock this Mac, then retry.": "钥匙串已锁定或无法交互。请解锁这台 Mac 后重试。",
  "macOS Keychain is unavailable. Restart the app; if it persists, open Keychain Access and check the login keychain.": "macOS 钥匙串不可用。请重启应用；如果问题仍然存在，请打开“钥匙串访问”检查登录钥匙串。",
  "First-run state is damaged. Your Keychain keys were not changed; retry setup or reinstall this app version.": "首次运行状态已损坏。钥匙串密钥未被修改；请重试设置或重新安装此版本。",
  "Hey Jarvis cannot write its Application Support settings. Check disk access and available space.": "Hey Jarvis 无法写入应用支持设置。请检查磁盘访问权限和可用空间。",
  "Smart Speaker preferences are damaged. The mode remains inactive until the settings file is repaired.": "智能音箱偏好设置已损坏。修复设置文件前，该模式将保持关闭。",
  "Hey Jarvis cannot save Smart Speaker preferences. Check disk access and available space.": "Hey Jarvis 无法保存智能音箱偏好设置。请检查磁盘访问权限和可用空间。",
  "Wake diagnostics enabled. It will apply when voice listening starts.": "唤醒调试日志已开启，将在语音监听启动时应用。",
  "Wake diagnostics disabled. It will apply when voice listening starts.": "唤醒调试日志已关闭，将在语音监听启动时应用。",
  "Wake tuning saved. It will apply when voice listening starts.": "唤醒参数已保存，将在语音监听启动时应用。",
  "On. Bounded numeric wake evidence is saved locally.": "已开启，有限的数值型唤醒证据会保存在本地。",
  "Off. No wake scores are saved.": "已关闭，不保存唤醒分数。",
  "Finish the key and microphone checks before starting the voice runtime.": "启动语音运行环境前，请完成密钥和麦克风检查。",
  "OpenAI rejected this key. Replace it with an active project key, then rerun the readiness check.": "OpenAI 拒绝了此密钥。请换成有效的项目密钥，然后重新运行就绪检查。",
  "OpenAI is temporarily unavailable. Listening remains off; retry the readiness check later.": "OpenAI 暂时不可用。监听保持关闭；请稍后重试就绪检查。",
  "OpenAI is unreachable. Check your internet connection, then run the readiness check again.": "无法连接 OpenAI。请检查网络连接，然后重新运行就绪检查。",
  "The local runtime did not become ready. Retry; if it repeats, quit and reopen Hey Jarvis.": "本地运行环境未能就绪。请重试；如果问题重复出现，请退出并重新打开 Hey Jarvis。",
  "The microphone check timed out. No stream was retained; retry after checking the selected input device.": "麦克风检查超时。没有保留音频流；请检查所选输入设备后重试。",
  "System Settings could not be opened. Open Privacy & Security → Microphone manually.": "无法打开系统设置。请手动打开“隐私与安全性 → 麦克风”。",
  "The local wake model is not ready. Restart the runtime; reinstall this app version if the error repeats.": "本地唤醒模型尚未就绪。请重启运行环境；如果错误重复出现，请重新安装此版本。",
  "The local runtime could not start. Retry, then quit and reopen Hey Jarvis if the problem continues.": "本地运行环境无法启动。请重试；如果问题持续存在，请退出并重新打开 Hey Jarvis。",
  "OpenAI key required before voice listening can start.": "开始语音监听前需要 OpenAI 密钥。",
  "Microphone access needs attention in System Settings.": "需要在系统设置中处理麦克风访问权限。",
  "OpenAI is configured. Complete the microphone check to start.": "OpenAI 已配置。请完成麦克风检查以启动。",
  "API key and microphone permission are ready.": "API 密钥和麦克风权限均已就绪。",
  "Stored in macOS Keychain. The value is never displayed.": "已存储在 macOS 钥匙串中，密钥内容不会显示。",
  "Not configured. A key is required before listening can start.": "尚未配置。开始监听前需要密钥。",
  "Stored in macOS Keychain. Stock quotes are enabled.": "已存储在 macOS 钥匙串中，股票报价已启用。",
  "Not configured. Other assistant features still work.": "尚未配置，助手的其他功能仍可使用。",
  "Replace key": "更换密钥",
  "Add key": "添加密钥",
  "Enabled. It activates only after you return and Wake listening is confirmed.": "已启用。返回助手并确认唤醒监听后才会生效。",
  "Off. Hey Jarvis follows normal Mac sleep behavior.": "已关闭。Hey Jarvis 遵循 Mac 的正常睡眠行为。",
  "Access was denied. Enable Hey Jarvis in Privacy & Security → Microphone, then retry.": "访问被拒绝。请在“隐私与安全性 → 麦克风”中启用 Hey Jarvis，然后重试。",
  "Access granted. Local wake listening continues unless you run a new microphone check.": "访问已允许。除非重新运行麦克风检查，否则本地唤醒监听会继续。",
  "Permission has not been checked yet.": "尚未检查权限。",
  "Runtime ready": "运行环境就绪",
  "Open the assistant to begin wake listening.": "打开助手以开始唤醒监听。",
  "Wake listening": "正在等待唤醒",
  "Listening continues while Settings is open.": "打开设置时监听仍会继续。",
  "Conversation active": "对话进行中",
  "The current conversation continues in the assistant window.": "当前对话会在助手窗口中继续。",
  "Resume required": "需要恢复",
  "Voice listening is off until you resume.": "恢复前，语音监听保持关闭。",
  "Open this page through the Hey Jarvis desktop app.": "请通过 Hey Jarvis 桌面应用打开此页面。",
  "A native secure entry window is open.": "原生安全输入窗口已打开。",
  "Saved in macOS Keychain. The change applies when voice listening starts.": "已保存到 macOS 钥匙串，将在语音监听启动时应用。",
  "No changes were made.": "未进行任何更改。",
  "Removed from macOS Keychain. Voice listening remains off until setup is ready again.": "已从 macOS 钥匙串移除。设置重新就绪前，语音监听保持关闭。",
  "Microphone access is required, but listening remains off. Enable it in System Settings and retry.": "需要麦克风访问权限，但监听仍保持关闭。请在系统设置中启用后重试。",
  "No microphone was found. Connect or enable an input device, then retry.": "未找到麦克风。请连接或启用输入设备后重试。",
  "The microphone check failed and listening remains off. Check the input device and retry.": "麦克风检查失败，监听保持关闭。请检查输入设备后重试。",
  "Access granted; the temporary check stream was released.": "访问已允许；临时检查音频流已释放。",
  "Checking the microphone…": "正在检查麦克风…",
  "Microphone access is ready. Pending changes apply when voice listening starts.": "麦克风访问已就绪，待处理的更改将在语音监听启动时应用。",
  "Add an OpenAI key before starting Hey Jarvis.": "启动 Hey Jarvis 前请先添加 OpenAI 密钥。",
  "Checking the built-in microphone…": "正在检查内置麦克风…",
  "Microphone access is ready. Starting the local voice runtime…": "麦克风访问已就绪。正在启动本地语音运行环境…",
  "Voice listening resumed. Settings can remain open.": "语音监听已恢复，设置窗口可以保持打开。",
  "Starting the local voice runtime…": "正在启动本地语音运行环境…",
  "Checking local setup…": "正在检查本地设置…",
  "Checking macOS Keychain…": "正在检查 macOS 钥匙串…",
  "Voice startup is taking longer than expected. Settings remains available.": "语音启动所需时间超出预期，设置仍可使用。",
  "Restarting local wake listening…": "正在重新启动本地唤醒监听…",
  "Apply & Done": "应用并完成",
  "Applying Settings changes…": "正在应用设置更改…",
  "Local setup is ready. Existing voice listening is unchanged.": "本地设置已就绪，现有语音监听不受影响。",
  "Setup needs attention. Review API Keys and Microphone before starting.": "设置需要处理。启动前请检查 API 密钥和麦克风。",
  "Smart Speaker Mode enabled. It will activate only during confirmed wake listening.": "智能音箱模式已启用，只会在确认唤醒监听时生效。",
  "Smart Speaker Mode disabled. Normal Mac sleep behavior is restored.": "智能音箱模式已关闭，Mac 已恢复正常睡眠行为。",
  "Support export was rejected or unavailable; diagnostics were not changed.": "支持导出被拒绝或不可用；诊断数据未被更改。",
  "Clear all local Hey Jarvis diagnostics? This cannot be undone.": "清除所有本地 Hey Jarvis 诊断数据？此操作无法撤销。",
  "Local diagnostics were cleared.": "本地诊断数据已清除。",
  "Diagnostics could not be cleared.": "无法清除诊断数据。",
}));

function ui(english) {
  return text(appLanguage, english, DYNAMIC_ZH.get(english) || english);
}

function setLocale(locale) {
  appLanguage = supportedLocale(locale);
  applyDocumentLocale(appLanguage);
  elements.appLanguage.value = appLanguage;
}

function setTheme(theme) {
  appTheme = theme === "day" ? "day" : "night";
  document.documentElement.dataset.theme = appTheme;
  document.documentElement.style.colorScheme = appTheme === "day" ? "light" : "dark";
  if (elements.appTheme) elements.appTheme.value = appTheme;
}

function renderWakeTuning(snapshot) {
  const threshold = snapshot.wake_threshold === 0.6 ? 0.6 : 0.5;
  const frames = snapshot.wake_confirmation_frames === 3 ? 3 : 2;
  elements.wakeThreshold.value = threshold.toFixed(1);
  elements.wakeConfirmationFrames.value = String(frames);
  elements.wakeTuningEffective.textContent = appLanguage === "zh-CN"
    ? `当前生效：阈值 ${threshold.toFixed(2)} · 连续 ${frames} 帧。`
    : `Effective: threshold ${threshold.toFixed(2)} · ${frames} consecutive frames.`;
}

function isSettingsWindow() {
  return window.location.hash === SETTINGS_HASH;
}

function isResumeRequired() {
  return window.location.hash === RESUME_REQUIRED_HASH;
}

function showResumeRequired() {
  elements.settingsShell.hidden = true;
  elements.returningView.hidden = true;
  elements.resumeView.hidden = false;
  elements.resumeVoice.disabled = false;
}

function afterCommittedPaint() {
  return new Promise(resolve => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
  });
}

function resetSettingsSurface() {
  elements.resumeView.hidden = true;
  elements.returningView.hidden = true;
  elements.settingsShell.hidden = false;
}

function showStartingRuntime() {
  elements.resumeView.hidden = true;
  elements.settingsShell.hidden = true;
  elements.returningView.hidden = false;
  elements.returningStatus.textContent = ui("Starting the local voice runtime…");
}

function recordLifecycle(event, sessionId = null) {
  if (!invoke) return Promise.resolve();
  return invoke("record_webview_lifecycle", { event, sessionId }).catch(() => {});
}

const recoveryMessages = {
  credential_format_invalid: "That key format is invalid. Copy the complete key without spaces and try again.",
  openai_credential_missing: "Add an OpenAI API key before starting Hey Jarvis.",
  keychain_auth_failed: "macOS denied Keychain access. Unlock your login keychain and try again.",
  keychain_interaction_not_allowed: "Keychain is locked or interaction is unavailable. Unlock this Mac, then retry.",
  keychain_unavailable: "macOS Keychain is unavailable. Restart the app; if it persists, open Keychain Access and check the login keychain.",
  onboarding_state_corrupt: "First-run state is damaged. Your Keychain keys were not changed; retry setup or reinstall this app version.",
  onboarding_state_unavailable: "Hey Jarvis cannot write its Application Support settings. Check disk access and available space.",
  preferences_corrupt: "Smart Speaker preferences are damaged. The mode remains inactive until the settings file is repaired.",
  preferences_unavailable: "Hey Jarvis cannot save Smart Speaker preferences. Check disk access and available space.",
  onboarding_incomplete: "Finish the key and microphone checks before starting the voice runtime.",
  openai_credential_invalid: "OpenAI rejected this key. Replace it with an active project key, then rerun the readiness check.",
  openai_service_unavailable: "OpenAI is temporarily unavailable. Listening remains off; retry the readiness check later.",
  offline: "OpenAI is unreachable. Check your internet connection, then run the readiness check again.",
  sidecar_readiness_timed_out: "The local runtime did not become ready. Retry; if it repeats, quit and reopen Hey Jarvis.",
  microphone_check_timed_out: "The microphone check timed out. No stream was retained; retry after checking the selected input device.",
  system_settings_unavailable: "System Settings could not be opened. Open Privacy & Security → Microphone manually.",
};

function friendlyError(error) {
  const value = String(error);
  for (const [code, message] of Object.entries(recoveryMessages)) {
    if (value.includes(code)) return ui(message);
  }
  if (value.includes("offline") || value.includes("network")) {
    return ui("OpenAI is unreachable. Check your internet connection, then run the readiness check again.");
  }
  if (value.includes("model") || value.includes("wake")) {
    return ui("The local wake model is not ready. Restart the runtime; reinstall this app version if the error repeats.");
  }
  return ui("The local runtime could not start. Retry, then quit and reopen Hey Jarvis if the problem continues.");
}

function activatePanel(name, focus = false) {
  for (const panel of elements.panels) panel.hidden = panel.dataset.settingsPanel !== name;
  for (const item of elements.navItems) {
    const active = item.dataset.panel === name;
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
  if (focus) document.querySelector(`[data-settings-panel="${name}"] h2`)?.focus();
}

function readinessText(snapshot) {
  if (snapshot.credential_status_pending) return ui("Checking local setup…");
  if (!snapshot.openai_configured) return ui("OpenAI key required before voice listening can start.");
  if (snapshot.microphone_permission === "denied") return ui("Microphone access needs attention in System Settings.");
  if (snapshot.microphone_permission !== "granted") return ui("OpenAI is configured. Complete the microphone check to start.");
  return ui("API key and microphone permission are ready.");
}

function renderSetup(snapshot) {
  setup = snapshot;
  setLocale(snapshot.app_language);
  setTheme(snapshot.app_theme);
  elements.openaiStatus.textContent = snapshot.credential_status_pending
    ? ui("Checking macOS Keychain…")
    : snapshot.openai_configured
    ? ui("Stored in macOS Keychain. The value is never displayed.")
    : ui("Not configured. A key is required before listening can start.");
  elements.finnhubStatus.textContent = snapshot.credential_status_pending
    ? ui("Checking macOS Keychain…")
    : snapshot.finnhub_configured
    ? ui("Stored in macOS Keychain. Stock quotes are enabled.")
    : ui("Not configured. Other assistant features still work.");
  elements.saveOpenai.textContent = ui(snapshot.openai_configured ? "Replace key" : "Add key");
  elements.saveFinnhub.textContent = ui(snapshot.finnhub_configured ? "Replace key" : "Add key");
  elements.saveOpenai.disabled = snapshot.credential_status_pending === true;
  elements.saveFinnhub.disabled = snapshot.credential_status_pending === true;
  elements.deleteOpenai.hidden = snapshot.credential_status_pending || !snapshot.openai_configured;
  elements.deleteFinnhub.hidden = snapshot.credential_status_pending || !snapshot.finnhub_configured;
  elements.start.disabled = snapshot.credential_status_pending || !snapshot.openai_configured;
  elements.returnAssistant.hidden = isSettingsWindow()
    ? false
    : !snapshot.completed || !snapshot.openai_configured;
  elements.readiness.textContent = readinessText(snapshot);
  elements.smartSpeakerMode.checked = snapshot.smart_speaker_mode === true;
  elements.smartSpeakerStatus.textContent = snapshot.smart_speaker_mode
    ? ui("Enabled. It activates only after you return and Wake listening is confirmed.")
    : ui("Off. Hey Jarvis follows normal Mac sleep behavior.");
  elements.wakeDiagnosticsEnabled.checked = snapshot.wake_diagnostics_enabled === true;
  elements.wakeDiagnosticsStatus.textContent = snapshot.wake_diagnostics_enabled
    ? ui("On. Bounded numeric wake evidence is saved locally.")
    : ui("Off. No wake scores are saved.");
  renderWakeTuning(snapshot);
  if (snapshot.microphone_permission === "denied") {
    elements.microphoneStatus.textContent = ui("Access was denied. Enable Hey Jarvis in Privacy & Security → Microphone, then retry.");
    elements.microphoneSettings.hidden = false;
  } else if (snapshot.microphone_permission === "granted") {
    elements.microphoneStatus.textContent = ui("Access granted. Local wake listening continues unless you run a new microphone check.");
    elements.microphoneSettings.hidden = true;
  } else {
    elements.microphoneStatus.textContent = ui("Permission has not been checked yet.");
    elements.microphoneSettings.hidden = true;
  }
  renderCompletionAction();
}

function canApplyPendingRuntimeChange() {
  return isSettingsWindow()
    && runtimeRestartNeeded
    && settingsEntryRuntimeIntent !== "inactive"
    && setup?.openai_configured === true
    && setup?.microphone_permission === "granted";
}

function renderCompletionAction() {
  if (!elements.returnAssistant || !isSettingsWindow()) return;
  elements.returnAssistant.textContent = ui("Apply & Done");
}

function requireRuntimeRestart() {
  runtimeRestartNeeded = true;
  applyRetryNeeded = false;
  renderCompletionAction();
}

async function showSettings() {
  try {
    await invoke("open_settings");
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

function renderVoiceStatus(snapshot) {
  const availability = snapshot?.availability || "resume_required";
  if (isSettingsWindow() && !settingsEntryAvailabilityCaptured) {
    settingsEntryAvailabilityCaptured = true;
    settingsEntryRuntimeIntent = availability === "wake_listening" || availability === "busy"
      ? "listening"
      : availability === "ready" ? "ready" : "inactive";
  } else if (isSettingsWindow()
    && settingsEntryRuntimeIntent === "ready"
    && (availability === "wake_listening" || availability === "busy")) {
    settingsEntryRuntimeIntent = "listening";
  }
  if (availability === lastVoiceAvailability) return;
  lastVoiceAvailability = availability;
  const labels = {
    ready: [ui("Runtime ready"), ui("Open the assistant to begin wake listening.")],
    wake_listening: [ui("Wake listening"), ui("Listening continues while Settings is open.")],
    busy: [ui("Conversation active"), ui("The current conversation continues in the assistant window.")],
    resume_required: [ui("Resume required"), ui("Voice listening is off until you resume.")],
  };
  const [label, summary] = labels[availability] || labels.resume_required;
  elements.voiceStatusLabel.textContent = label;
  elements.voiceStatusDetail.textContent = summary;
}

async function refreshVoiceStatus() {
  if (!isSettingsWindow()) return;
  try {
    renderVoiceStatus(await invoke("sidecar_status"));
  } catch (_error) {
    renderVoiceStatus({ availability: "resume_required" });
  }
}

async function waitForAppliedRuntime(expectedAvailability = settingsEntryRuntimeIntent === "listening"
  ? "wake_listening"
  : "ready") {
  const deadline = Date.now() + 15000;
  let snapshot;
  do {
    await new Promise(resolve => window.setTimeout(resolve, 500));
    snapshot = await invoke("sidecar_status");
    renderVoiceStatus(snapshot);
  } while (snapshot.availability !== expectedAvailability && Date.now() < deadline);
  if (snapshot.availability !== expectedAvailability) throw new Error("sidecar_readiness_timed_out");
  runtimeRestartNeeded = false;
  applyRetryNeeded = false;
  renderCompletionAction();
  renderVoiceStatus(snapshot);
}

function navigateToAssistant(snapshot, { recovery = false } = {}) {
  if (snapshot.state !== "ready" || !snapshot.control_url) {
    throw new Error(snapshot.detail || "sidecar_readiness_timed_out");
  }
  const endpoint = new URL(snapshot.control_url);
  if (endpoint.protocol !== "http:" || endpoint.hostname !== "127.0.0.1") {
    throw new Error("Sidecar returned an invalid control endpoint.");
  }
  if (recovery) endpoint.hash = "smart-speaker-resume";
  else if (setup?.smart_speaker_mode === true) endpoint.hash = "smart-speaker-mode";
  recordLifecycle("runtime_navigation", snapshot.session_id);
  window.location.assign(endpoint.href);
}

async function waitForStartupRuntime() {
  const deadline = Date.now() + 30000;
  while (await invoke("startup_runtime_pending")) {
    if (Date.now() >= deadline) {
      elements.returningStatus.textContent = ui("Voice startup is taking longer than expected. Settings remains available.");
      return;
    }
    await new Promise(resolve => window.setTimeout(resolve, 100));
  }
  const runtime = await invoke("sidecar_status");
  if (runtime.state === "ready") {
    navigateToAssistant(runtime);
    return;
  }

  const snapshot = await invoke("onboarding_status");
  renderSetup(snapshot);
  resetSettingsSurface();
  if (!snapshot.openai_configured) activatePanel("api-keys");
  elements.message.textContent = friendlyError(runtime.detail || "sidecar_readiness_timed_out");
}

async function refreshPendingCredentialStatus() {
  while (setup?.credential_status_pending) {
    await new Promise(resolve => window.setTimeout(resolve, 500));
    try {
      renderSetup(await invoke("enter_settings"));
    } catch (_error) {
      return;
    }
  }
}

async function load() {
  if (!invoke) {
    elements.message.textContent = ui("Open this page through the Hey Jarvis desktop app.");
    return;
  }
  try {
    recordStartup("dom_ready");
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => recordStartup("first_paint")));
    recordLifecycle("loaded");
    if (isResumeRequired()) {
      renderSetup(await invoke("onboarding_status"));
      showResumeRequired();
      return;
    }
    const settingsMode = isSettingsWindow();
    if (settingsMode) {
      resetSettingsSurface();
      await afterCommittedPaint();
    } else {
      showStartingRuntime();
      await afterCommittedPaint();
      recordStartup("shell_interactive");
      const route = await invoke("startup_route");
      setLocale(route.app_language);
      setTheme(route.app_theme);
      if (route.completed && route.microphone_permission === "granted") {
        await waitForStartupRuntime();
        return;
      }
      resetSettingsSurface();
    }
    const snapshot = await invoke(settingsMode ? "enter_settings" : "onboarding_status");
    renderSetup(snapshot);
    if (settingsMode) recordStartup("shell_interactive");
    if (settingsMode) {
      recordLifecycle("settings_opened");
      if (snapshot.credential_status_pending) void refreshPendingCredentialStatus();
      await refreshVoiceStatus();
      window.setInterval(refreshVoiceStatus, 1000);
    }
    if (!settingsMode && snapshot.completed && snapshot.openai_configured) {
      navigateToAssistant(await invoke("sidecar_status"));
    } else if (!snapshot.openai_configured) {
      activatePanel("api-keys");
    }
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function saveCredential(kind) {
  elements.message.textContent = ui("A native secure entry window is open.");
  try {
    await invoke("prompt_save_credential", { kind });
    requireRuntimeRestart();
    renderSetup(await invoke("onboarding_status"));
    await refreshVoiceStatus();
    elements.message.textContent = ui("Saved in macOS Keychain. The change applies when voice listening starts.");
  } catch (error) {
    elements.message.textContent = String(error).includes("credential_prompt_cancelled")
      ? ui("No changes were made.")
      : friendlyError(error);
  }
}

async function deleteCredential(kind) {
  const label = kind === "openai" ? "OpenAI" : "Finnhub";
  const confirmation = appLanguage === "zh-CN"
    ? `从 macOS 钥匙串中删除 ${label} 密钥？`
    : `Delete the ${label} key from macOS Keychain?`;
  if (!window.confirm(confirmation)) return;
  try {
    await invoke("delete_credential", { kind });
    requireRuntimeRestart();
    renderSetup(await invoke("onboarding_status"));
    await refreshVoiceStatus();
    elements.message.textContent = ui("Removed from macOS Keychain. Voice listening remains off until setup is ready again.");
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function acquireMicrophone() {
  recordLifecycle("microphone_check_started");
  let stream;
  try {
    await invoke("prepare_microphone_check");
    requireRuntimeRestart();
    await refreshVoiceStatus();
    let timedOut = false;
    let timeoutId;
    const mediaRequest = navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    }).then(result => {
      if (timedOut) {
        for (const track of result.getTracks()) track.stop();
        throw new Error("microphone_check_timed_out");
      }
      return result;
    });
    try {
      stream = await Promise.race([
        mediaRequest,
        new Promise((_, reject) => {
          timeoutId = window.setTimeout(() => {
            timedOut = true;
            reject(new Error("microphone_check_timed_out"));
          }, 15000);
        }),
      ]);
    } finally {
      window.clearTimeout(timeoutId);
    }
  } catch (error) {
    if (error?.name === "NotAllowedError" || error?.name === "SecurityError") {
      renderSetup(await invoke("record_microphone_denied"));
      recordLifecycle("microphone_denied");
      elements.message.textContent = ui("Microphone access is required, but listening remains off. Enable it in System Settings and retry.");
    } else if (String(error).includes("microphone_check_timed_out")) {
      elements.message.textContent = ui(recoveryMessages.microphone_check_timed_out);
    } else if (error?.name === "NotFoundError") {
      elements.message.textContent = ui("No microphone was found. Connect or enable an input device, then retry.");
    } else {
      elements.message.textContent = ui("The microphone check failed and listening remains off. Check the input device and retry.");
    }
    return false;
  }
  for (const track of stream.getTracks()) track.stop();
  recordLifecycle("microphone_check_passed");
  elements.microphoneStatus.textContent = ui("Access granted; the temporary check stream was released.");
  return true;
}

async function checkMicrophoneOnly() {
  elements.message.textContent = ui("Checking the microphone…");
  if (!await acquireMicrophone()) return;
  renderSetup(await invoke("record_microphone_granted"));
  await refreshVoiceStatus();
  elements.message.textContent = ui("Microphone access is ready. Pending changes apply when voice listening starts.");
}

async function checkMicrophoneAndStart() {
  if (!setup?.openai_configured) {
    activatePanel("api-keys");
    elements.message.textContent = ui("Add an OpenAI key before starting Hey Jarvis.");
    return;
  }
  elements.message.textContent = ui("Checking the built-in microphone…");
  if (!await acquireMicrophone()) return;
  elements.message.textContent = ui("Microphone access is ready. Starting the local voice runtime…");
  try {
    if (isSettingsWindow()) {
      renderSetup(await invoke("record_microphone_granted"));
      await invoke("restart_voice_from_settings", { resumeListening: true });
      await waitForAppliedRuntime("wake_listening");
      elements.message.textContent = ui("Voice listening resumed. Settings can remain open.");
    } else {
      navigateToAssistant(await invoke("complete_onboarding"));
    }
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function returnToAssistant() {
  if (isSettingsWindow()) {
    if (canApplyPendingRuntimeChange()) {
      elements.returnAssistant.disabled = true;
      elements.message.textContent = ui("Applying Settings changes…");
      try {
        await recordLifecycle("runtime_restart_requested");
        await invoke("restart_voice_from_settings", {
          resumeListening: settingsEntryRuntimeIntent === "listening",
        });
        await waitForAppliedRuntime();
        await invoke("close_settings_window");
      } catch (error) {
        applyRetryNeeded = true;
        elements.message.textContent = friendlyError(error);
        renderCompletionAction();
        elements.returnAssistant.focus();
      } finally {
        elements.returnAssistant.disabled = false;
      }
      return;
    }
    try {
      await invoke("close_settings_window");
    } catch (error) {
      elements.message.textContent = friendlyError(error);
    }
    return;
  }
  elements.settingsShell.hidden = true;
  elements.returningView.hidden = false;
  elements.returningStatus.textContent = ui("Starting the local voice runtime…");
  try {
    await recordLifecycle("runtime_restart_requested");
    navigateToAssistant(await invoke("restart_sidecar"));
  } catch (error) {
    elements.returningView.hidden = true;
    elements.settingsShell.hidden = false;
    elements.message.textContent = friendlyError(error);
    elements.returnAssistant.focus();
  }
}

async function resumeVoiceAssistant() {
  elements.resumeVoice.disabled = true;
  elements.resumeStatus.textContent = ui("Restarting local wake listening…");
  try {
    await recordLifecycle("runtime_restart_requested");
    navigateToAssistant(await invoke("resume_voice_assistant"), { recovery: true });
  } catch (error) {
    elements.resumeVoice.disabled = false;
    elements.resumeStatus.textContent = friendlyError(error);
    elements.resumeVoice.focus();
  }
}

async function runReadinessCheck() {
  try {
    const snapshot = await invoke("onboarding_status");
    renderSetup(snapshot);
    elements.message.textContent = snapshot.openai_configured && snapshot.microphone_permission === "granted"
      ? ui("Local setup is ready. Existing voice listening is unchanged.")
      : ui("Setup needs attention. Review API Keys and Microphone before starting.");
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function setSmartSpeakerMode() {
  const enabled = elements.smartSpeakerMode.checked;
  elements.smartSpeakerMode.disabled = true;
  try {
    renderSetup(await invoke("set_smart_speaker_mode", { enabled }));
    elements.message.textContent = enabled
      ? ui("Smart Speaker Mode enabled. It will activate only during confirmed wake listening.")
      : ui("Smart Speaker Mode disabled. Normal Mac sleep behavior is restored.");
  } catch (error) {
    elements.smartSpeakerMode.checked = !enabled;
    elements.message.textContent = friendlyError(error);
  } finally {
    elements.smartSpeakerMode.disabled = false;
  }
}

async function setWakeDiagnostics() {
  const enabled = elements.wakeDiagnosticsEnabled.checked;
  elements.wakeDiagnosticsEnabled.disabled = true;
  try {
    const snapshot = await invoke("set_wake_diagnostics", { enabled });
    requireRuntimeRestart();
    renderSetup(snapshot);
    await refreshVoiceStatus();
    elements.message.textContent = ui(enabled
      ? "Wake diagnostics enabled. It will apply when voice listening starts."
      : "Wake diagnostics disabled. It will apply when voice listening starts.");
  } catch (error) {
    elements.wakeDiagnosticsEnabled.checked = !enabled;
    elements.message.textContent = friendlyError(error);
  } finally {
    elements.wakeDiagnosticsEnabled.disabled = false;
  }
}

async function setWakeTuning() {
  const wakeThreshold = Number(elements.wakeThreshold.value);
  const wakeConfirmationFrames = Number(elements.wakeConfirmationFrames.value);
  const changed = setup?.wake_threshold !== wakeThreshold
    || setup?.wake_confirmation_frames !== wakeConfirmationFrames;
  elements.wakeThreshold.disabled = true;
  elements.wakeConfirmationFrames.disabled = true;
  try {
    const snapshot = await invoke("set_wake_tuning", {
      wakeThreshold,
      wakeConfirmationFrames,
    });
    if (changed) requireRuntimeRestart();
    renderSetup(snapshot);
    await refreshVoiceStatus();
    elements.message.textContent = ui("Wake tuning saved. It will apply when voice listening starts.");
  } catch (error) {
    if (setup) renderWakeTuning(setup);
    elements.message.textContent = friendlyError(error);
  } finally {
    elements.wakeThreshold.disabled = false;
    elements.wakeConfirmationFrames.disabled = false;
  }
}

async function exportSupport() {
  try {
    const result = await invoke("export_support_bundle");
    elements.diagnosticsMessage.textContent = appLanguage === "zh-CN"
      ? `支持包已导出（${result.records} 个事件，${result.bytes} 字节）：${result.path}`
      : `Support bundle exported (${result.records} events, ${result.bytes} bytes): ${result.path}`;
  } catch (_error) {
    elements.diagnosticsMessage.textContent = ui("Support export was rejected or unavailable; diagnostics were not changed.");
  }
}

async function setAppLanguage() {
  const previous = appLanguage;
  elements.appLanguage.disabled = true;
  try {
    const snapshot = await invoke("set_app_language", { locale: elements.appLanguage.value });
    lastVoiceAvailability = null;
    renderSetup(snapshot);
    await refreshVoiceStatus();
    elements.message.textContent = appLanguage === "zh-CN"
      ? "应用语言已更新。固定语音提示将在下一次唤醒时使用中文。"
      : "App language updated. Fixed voice cues will use English on the next wake.";
  } catch (error) {
    setLocale(previous);
    elements.message.textContent = friendlyError(error);
  } finally {
    elements.appLanguage.disabled = false;
  }
}

async function setAppTheme() {
  const previous = appTheme;
  elements.appTheme.disabled = true;
  try {
    const snapshot = await invoke("set_app_theme", { theme: elements.appTheme.value });
    renderSetup(snapshot);
  } catch (error) {
    setTheme(previous);
    elements.message.textContent = friendlyError(error);
  } finally {
    elements.appTheme.disabled = false;
  }
}

for (const item of elements.navItems) {
  item.addEventListener("click", () => activatePanel(item.dataset.panel, true));
}
elements.saveOpenai.addEventListener("click", () => saveCredential("openai"));
elements.saveFinnhub.addEventListener("click", () => saveCredential("finnhub"));
elements.deleteOpenai.addEventListener("click", () => deleteCredential("openai"));
elements.deleteFinnhub.addEventListener("click", () => deleteCredential("finnhub"));
elements.start.addEventListener("click", checkMicrophoneAndStart);
elements.microphoneCheck.addEventListener("click", checkMicrophoneOnly);
elements.returnAssistant.addEventListener("click", returnToAssistant);
elements.resumeVoice.addEventListener("click", resumeVoiceAssistant);
elements.resumeSettings.addEventListener("click", showSettings);
elements.returningSettings.addEventListener("click", showSettings);
elements.readinessCheck.addEventListener("click", runReadinessCheck);
elements.smartSpeakerMode.addEventListener("change", setSmartSpeakerMode);
elements.wakeDiagnosticsEnabled.addEventListener("change", setWakeDiagnostics);
elements.wakeThreshold.addEventListener("change", setWakeTuning);
elements.wakeConfirmationFrames.addEventListener("change", setWakeTuning);
elements.appLanguage.addEventListener("change", setAppLanguage);
elements.appTheme.addEventListener("change", setAppTheme);
elements.microphoneSettings.addEventListener("click", async () => {
  try {
    await invoke("open_microphone_settings");
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
});
elements.exportSupport.addEventListener("click", exportSupport);
elements.clearDiagnostics.addEventListener("click", async () => {
  if (!window.confirm(ui("Clear all local Hey Jarvis diagnostics? This cannot be undone."))) return;
  try {
    await invoke("clear_diagnostics");
    elements.diagnosticsMessage.textContent = ui("Local diagnostics were cleared.");
  } catch (_error) {
    elements.diagnosticsMessage.textContent = ui("Diagnostics could not be cleared.");
  }
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted && isSettingsWindow()) refreshVoiceStatus();
});
window.addEventListener("pagehide", () => {
  recordLifecycle("pagehide");
});

load();

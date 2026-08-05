const invoke = window.__TAURI__?.core?.invoke;

const elements = {
  resumeView: document.querySelector("#resume-view"),
  resumeVoice: document.querySelector("#resume-voice"),
  resumeSettings: document.querySelector("#resume-settings"),
  resumeStatus: document.querySelector("#resume-status"),
  settingsShell: document.querySelector("#settings-shell"),
  returningView: document.querySelector("#returning-view"),
  returningStatus: document.querySelector("#returning-status"),
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
  exportSupport: document.querySelector("#export-support"),
  clearDiagnostics: document.querySelector("#clear-diagnostics"),
  diagnosticsMessage: document.querySelector("#diagnostics-message"),
};

let setup = null;
const SETTINGS_RETURN_HASH = "#settings-return";
const RESUME_REQUIRED_HASH = "#resume-required";

function isSettingsReturn() {
  return window.location.hash === SETTINGS_RETURN_HASH;
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
  system_settings_unavailable: "System Settings could not be opened. Open Privacy & Security → Microphone manually.",
};

function friendlyError(error) {
  const value = String(error);
  for (const [code, message] of Object.entries(recoveryMessages)) {
    if (value.includes(code)) return message;
  }
  if (value.includes("offline") || value.includes("network")) {
    return "OpenAI is unreachable. Check your internet connection, then run the readiness check again.";
  }
  if (value.includes("model") || value.includes("wake")) {
    return "The local wake model is not ready. Restart the runtime; reinstall this app version if the error repeats.";
  }
  return "The local runtime could not start. Retry, then quit and reopen Hey Jarvis if the problem continues.";
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
  if (!snapshot.openai_configured) return "OpenAI key required before voice listening can start.";
  if (snapshot.microphone_permission === "denied") return "Microphone access needs attention in System Settings.";
  if (snapshot.microphone_permission !== "granted") return "OpenAI is configured. Complete the microphone check to start.";
  return "API key and microphone permission are ready.";
}

function renderSetup(snapshot) {
  setup = snapshot;
  elements.openaiStatus.textContent = snapshot.openai_configured
    ? "Stored in macOS Keychain. The value is never displayed."
    : "Not configured. A key is required before listening can start.";
  elements.finnhubStatus.textContent = snapshot.finnhub_configured
    ? "Stored in macOS Keychain. Stock quotes are enabled."
    : "Not configured. Other assistant features still work.";
  elements.saveOpenai.textContent = snapshot.openai_configured ? "Replace key" : "Add key";
  elements.saveFinnhub.textContent = snapshot.finnhub_configured ? "Replace key" : "Add key";
  elements.deleteOpenai.hidden = !snapshot.openai_configured;
  elements.deleteFinnhub.hidden = !snapshot.finnhub_configured;
  elements.start.disabled = !snapshot.openai_configured;
  elements.returnAssistant.hidden = !snapshot.completed || !snapshot.openai_configured;
  elements.readiness.textContent = readinessText(snapshot);
  elements.smartSpeakerMode.checked = snapshot.smart_speaker_mode === true;
  elements.smartSpeakerStatus.textContent = snapshot.smart_speaker_mode
    ? "Enabled. It activates only after you return and Wake listening is confirmed."
    : "Off. Hey Jarvis follows normal Mac sleep behavior.";
  if (snapshot.microphone_permission === "denied") {
    elements.microphoneStatus.textContent = "Access was denied. Enable Hey Jarvis in Privacy & Security → Microphone, then retry.";
    elements.microphoneSettings.hidden = false;
  } else if (snapshot.microphone_permission === "granted") {
    elements.microphoneStatus.textContent = "Access granted. Settings is not using the microphone.";
    elements.microphoneSettings.hidden = true;
  } else {
    elements.microphoneStatus.textContent = "Permission has not been checked yet.";
    elements.microphoneSettings.hidden = true;
  }
}

async function showSettings() {
  resetSettingsSurface();
  try {
    if (!isSettingsReturn()) window.history.replaceState(null, "", SETTINGS_RETURN_HASH);
    await afterCommittedPaint();
    renderSetup(await invoke("enter_settings"));
    recordLifecycle("settings_opened");
    elements.message.textContent = "Voice listening is stopped while Settings is open.";
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
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
  window.history.replaceState(null, "", SETTINGS_RETURN_HASH);
  recordLifecycle("runtime_navigation", snapshot.session_id);
  window.location.assign(endpoint.href);
}

async function load() {
  if (!invoke) {
    elements.message.textContent = "Open this page through the Hey Jarvis desktop app.";
    return;
  }
  try {
    recordLifecycle("loaded");
    if (isResumeRequired()) {
      showResumeRequired();
      return;
    }
    const settingsMode = isSettingsReturn();
    if (settingsMode) {
      resetSettingsSurface();
      await afterCommittedPaint();
    }
    const snapshot = await invoke(settingsMode ? "enter_settings" : "onboarding_status");
    renderSetup(snapshot);
    if (settingsMode) {
      recordLifecycle("settings_opened");
      elements.message.textContent = "Voice listening is stopped while Settings is open.";
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
  elements.message.textContent = "A native secure entry window is open.";
  try {
    await invoke("prompt_save_credential", { kind });
    renderSetup(await invoke("onboarding_status"));
    elements.message.textContent = "Saved in macOS Keychain.";
  } catch (error) {
    elements.message.textContent = String(error).includes("credential_prompt_cancelled")
      ? "No changes were made."
      : friendlyError(error);
  }
}

async function deleteCredential(kind) {
  const label = kind === "openai" ? "OpenAI" : "Finnhub";
  if (!window.confirm(`Delete the ${label} key from macOS Keychain?`)) return;
  try {
    await invoke("delete_credential", { kind });
    renderSetup(await invoke("onboarding_status"));
    elements.message.textContent = "Removed from macOS Keychain.";
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function acquireMicrophone() {
  recordLifecycle("microphone_check_started");
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (error) {
    if (error?.name === "NotAllowedError" || error?.name === "SecurityError") {
      renderSetup(await invoke("record_microphone_denied"));
      recordLifecycle("microphone_denied");
      elements.message.textContent = "Microphone access is required, but listening remains off. Enable it in System Settings and retry.";
    } else if (error?.name === "NotFoundError") {
      elements.message.textContent = "No microphone was found. Connect or enable an input device, then retry.";
    } else {
      elements.message.textContent = "The microphone check failed and listening remains off. Check the input device and retry.";
    }
    return false;
  }
  for (const track of stream.getTracks()) track.stop();
  recordLifecycle("microphone_check_passed");
  elements.microphoneStatus.textContent = "Access granted; the temporary check stream was released.";
  return true;
}

async function checkMicrophoneOnly() {
  elements.message.textContent = "Checking the microphone…";
  if (!await acquireMicrophone()) return;
  renderSetup(await invoke("record_microphone_granted"));
  elements.message.textContent = "Microphone access is ready. Settings is not listening.";
}

async function checkMicrophoneAndStart() {
  if (!setup?.openai_configured) {
    activatePanel("api-keys");
    elements.message.textContent = "Add an OpenAI key before starting Hey Jarvis.";
    return;
  }
  elements.message.textContent = "Checking the built-in microphone…";
  if (!await acquireMicrophone()) return;
  elements.message.textContent = "Microphone access is ready. Starting the local voice runtime…";
  try {
    navigateToAssistant(await invoke("complete_onboarding"));
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function returnToAssistant() {
  elements.settingsShell.hidden = true;
  elements.returningView.hidden = false;
  elements.returningStatus.textContent = "Starting the local voice runtime…";
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
  elements.resumeStatus.textContent = "Restarting local wake listening…";
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
      ? "Local setup is ready. Listening remains off until you return to the assistant."
      : "Setup needs attention. Review API Keys and Microphone before starting.";
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
      ? "Smart Speaker Mode enabled. It will activate only during confirmed wake listening."
      : "Smart Speaker Mode disabled. Normal Mac sleep behavior is restored.";
  } catch (error) {
    elements.smartSpeakerMode.checked = !enabled;
    elements.message.textContent = friendlyError(error);
  } finally {
    elements.smartSpeakerMode.disabled = false;
  }
}

async function exportSupport() {
  try {
    const result = await invoke("export_support_bundle");
    elements.diagnosticsMessage.textContent = `Support bundle exported (${result.records} events, ${result.bytes} bytes): ${result.path}`;
  } catch (_error) {
    elements.diagnosticsMessage.textContent = "Support export was rejected or unavailable; diagnostics were not changed.";
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
elements.readinessCheck.addEventListener("click", runReadinessCheck);
elements.smartSpeakerMode.addEventListener("change", setSmartSpeakerMode);
elements.microphoneSettings.addEventListener("click", async () => {
  try {
    await invoke("open_microphone_settings");
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
});
elements.exportSupport.addEventListener("click", exportSupport);
elements.clearDiagnostics.addEventListener("click", async () => {
  if (!window.confirm("Clear all local Hey Jarvis diagnostics? This cannot be undone.")) return;
  try {
    await invoke("clear_diagnostics");
    elements.diagnosticsMessage.textContent = "Local diagnostics were cleared.";
  } catch (_error) {
    elements.diagnosticsMessage.textContent = "Diagnostics could not be cleared.";
  }
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted && isSettingsReturn()) showSettings();
});
window.addEventListener("pagehide", () => {
  if (isSettingsReturn()) resetSettingsSurface();
  recordLifecycle("pagehide");
});

load();

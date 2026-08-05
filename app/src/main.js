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
  restartVoice: document.querySelector("#restart-voice"),
  pageSummary: document.querySelector("#page-summary"),
  voiceStatus: document.querySelector("#voice-status"),
  exportSupport: document.querySelector("#export-support"),
  clearDiagnostics: document.querySelector("#clear-diagnostics"),
  diagnosticsMessage: document.querySelector("#diagnostics-message"),
};

let setup = null;
let lastVoiceAvailability = null;
let runtimeRestartNeeded = false;
const SETTINGS_HASH = "#settings";
const RESUME_REQUIRED_HASH = "#resume-required";

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
  elements.returnAssistant.hidden = isSettingsWindow()
    ? false
    : !snapshot.completed || !snapshot.openai_configured;
  elements.readiness.textContent = readinessText(snapshot);
  elements.smartSpeakerMode.checked = snapshot.smart_speaker_mode === true;
  elements.smartSpeakerStatus.textContent = snapshot.smart_speaker_mode
    ? "Enabled. It activates only after you return and Wake listening is confirmed."
    : "Off. Hey Jarvis follows normal Mac sleep behavior.";
  if (snapshot.microphone_permission === "denied") {
    elements.microphoneStatus.textContent = "Access was denied. Enable Hey Jarvis in Privacy & Security → Microphone, then retry.";
    elements.microphoneSettings.hidden = false;
  } else if (snapshot.microphone_permission === "granted") {
    elements.microphoneStatus.textContent = "Access granted. Local wake listening continues unless you run a new microphone check.";
    elements.microphoneSettings.hidden = true;
  } else {
    elements.microphoneStatus.textContent = "Permission has not been checked yet.";
    elements.microphoneSettings.hidden = true;
  }
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
  if (availability === "resume_required" && setup?.completed && setup?.openai_configured) {
    runtimeRestartNeeded = true;
  }
  elements.restartVoice.hidden = !runtimeRestartNeeded || availability === "wake_listening" || !setup?.openai_configured;
  if (availability === lastVoiceAvailability) return;
  lastVoiceAvailability = availability;
  const labels = {
    ready: ["Runtime ready", "The local runtime is ready and will begin wake listening after the main window arms."],
    wake_listening: ["Wake listening", "Wake listening remains active while Settings is open."],
    busy: ["Conversation active", "The current voice conversation continues while Settings is open."],
    resume_required: ["Resume required", "Voice listening is off. Resume after finishing any runtime-affecting change."],
  };
  const [label, summary] = labels[availability] || labels.resume_required;
  elements.pageSummary.textContent = summary;
  elements.voiceStatus.textContent = `${label} — ${summary}`;
}

async function refreshVoiceStatus() {
  if (!isSettingsWindow()) return;
  try {
    renderVoiceStatus(await invoke("sidecar_status"));
  } catch (_error) {
    renderVoiceStatus({ availability: "resume_required" });
  }
}

async function waitForWakeListening() {
  const deadline = Date.now() + 15000;
  let snapshot;
  do {
    await new Promise(resolve => window.setTimeout(resolve, 500));
    snapshot = await invoke("sidecar_status");
    renderVoiceStatus(snapshot);
  } while (snapshot.availability !== "wake_listening" && Date.now() < deadline);
  if (snapshot.availability !== "wake_listening") throw new Error("sidecar_readiness_timed_out");
  runtimeRestartNeeded = false;
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
    const settingsMode = isSettingsWindow();
    if (settingsMode) {
      resetSettingsSurface();
      await afterCommittedPaint();
    }
    const snapshot = await invoke(settingsMode ? "enter_settings" : "onboarding_status");
    renderSetup(snapshot);
    if (settingsMode) {
      recordLifecycle("settings_opened");
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
  elements.message.textContent = "A native secure entry window is open.";
  try {
    await invoke("prompt_save_credential", { kind });
    runtimeRestartNeeded = true;
    renderSetup(await invoke("onboarding_status"));
    await refreshVoiceStatus();
    elements.message.textContent = "Saved in macOS Keychain. Resume voice listening when you are ready.";
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
    runtimeRestartNeeded = true;
    renderSetup(await invoke("onboarding_status"));
    await refreshVoiceStatus();
    elements.message.textContent = "Removed from macOS Keychain. Voice listening remains off until setup is ready again.";
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function acquireMicrophone() {
  recordLifecycle("microphone_check_started");
  let stream;
  try {
    await invoke("prepare_microphone_check");
    runtimeRestartNeeded = true;
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
      elements.message.textContent = "Microphone access is required, but listening remains off. Enable it in System Settings and retry.";
    } else if (String(error).includes("microphone_check_timed_out")) {
      elements.message.textContent = recoveryMessages.microphone_check_timed_out;
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
  await refreshVoiceStatus();
  elements.message.textContent = "Microphone access is ready. Resume voice listening when you are ready.";
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
    if (isSettingsWindow()) {
      renderSetup(await invoke("record_microphone_granted"));
      await invoke("restart_voice_from_settings");
      await waitForWakeListening();
      elements.message.textContent = "Voice listening resumed. Settings can remain open.";
    } else {
      navigateToAssistant(await invoke("complete_onboarding"));
    }
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function returnToAssistant() {
  if (isSettingsWindow()) {
    try {
      await invoke("close_settings_window");
    } catch (error) {
      elements.message.textContent = friendlyError(error);
    }
    return;
  }
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

async function restartVoiceFromSettings() {
  elements.restartVoice.disabled = true;
  elements.message.textContent = "Restarting local wake listening…";
  try {
    await recordLifecycle("runtime_restart_requested");
    await invoke("restart_voice_from_settings");
    await waitForWakeListening();
    elements.message.textContent = "Voice listening resumed. Settings can remain open.";
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  } finally {
    elements.restartVoice.disabled = false;
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
      ? "Local setup is ready. Existing voice listening is unchanged."
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
elements.restartVoice.addEventListener("click", restartVoiceFromSettings);
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
  if (event.persisted && isSettingsWindow()) refreshVoiceStatus();
});
window.addEventListener("pagehide", () => {
  recordLifecycle("pagehide");
});

load();

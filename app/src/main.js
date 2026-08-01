const invoke = window.__TAURI__?.core?.invoke;

const elements = {
  onboarding: document.querySelector("#onboarding"),
  runtime: document.querySelector("#runtime"),
  openaiStatus: document.querySelector("#openai-status"),
  finnhubStatus: document.querySelector("#finnhub-status"),
  microphoneStatus: document.querySelector("#microphone-status"),
  message: document.querySelector("#setup-message"),
  saveOpenai: document.querySelector("#save-openai"),
  deleteOpenai: document.querySelector("#delete-openai"),
  saveFinnhub: document.querySelector("#save-finnhub"),
  deleteFinnhub: document.querySelector("#delete-finnhub"),
  start: document.querySelector("#start"),
  microphoneSettings: document.querySelector("#microphone-settings"),
  dot: document.querySelector("#status-dot"),
  title: document.querySelector("#status-title"),
  detail: document.querySelector("#status-detail"),
  protocol: document.querySelector("#protocol"),
  session: document.querySelector("#session"),
  appSupport: document.querySelector("#app-support"),
  health: document.querySelector("#health-check"),
  restart: document.querySelector("#restart"),
  runtimeSettings: document.querySelector("#runtime-settings"),
};

let setup = null;
const SETTINGS_RETURN_HASH = "#settings-return";

function isSettingsReturn() {
  return window.location.hash === SETTINGS_RETURN_HASH;
}

const recoveryMessages = {
  credential_format_invalid: "That key format is invalid. Copy the complete key without spaces and try again.",
  openai_credential_missing: "Add an OpenAI API key before starting Hey Jarvis.",
  keychain_auth_failed: "macOS denied Keychain access. Unlock your login keychain and try again.",
  keychain_interaction_not_allowed: "Keychain is locked or interaction is unavailable. Unlock this Mac, then retry.",
  keychain_unavailable: "macOS Keychain is unavailable. Restart the app; if it persists, open Keychain Access and check the login keychain.",
  onboarding_state_corrupt: "First-run state is damaged. Your Keychain keys were not changed; retry setup or reinstall this app version.",
  onboarding_state_unavailable: "Hey Jarvis cannot write its Application Support settings. Check disk access and available space.",
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

function renderSetup(snapshot) {
  setup = snapshot;
  elements.onboarding.hidden = false;
  elements.runtime.hidden = true;
  elements.openaiStatus.textContent = snapshot.openai_configured
    ? "Stored in macOS Keychain. The value is never displayed."
    : "Not configured. A key is required before listening can start.";
  elements.finnhubStatus.textContent = snapshot.finnhub_configured
    ? "Stored in macOS Keychain. Stock quotes are enabled."
    : "Not configured. Other assistant features still work.";
  elements.saveOpenai.textContent = snapshot.openai_configured ? "Replace key…" : "Add key…";
  elements.saveFinnhub.textContent = snapshot.finnhub_configured ? "Replace key…" : "Add key…";
  elements.deleteOpenai.hidden = !snapshot.openai_configured;
  elements.deleteFinnhub.hidden = !snapshot.finnhub_configured;
  elements.start.disabled = !snapshot.openai_configured;
  if (snapshot.microphone_permission === "denied") {
    elements.microphoneStatus.textContent = "Microphone access was denied. Enable Hey Jarvis in Privacy & Security → Microphone, then retry.";
    elements.microphoneSettings.hidden = false;
  } else if (snapshot.microphone_permission === "granted") {
    elements.microphoneStatus.textContent = "Microphone access was granted. You can rerun the check at any time.";
  } else {
    elements.microphoneStatus.textContent = "Permission is requested only when you click Check microphone & start.";
    elements.microphoneSettings.hidden = true;
  }
}

async function showSettings() {
  try {
    if (!isSettingsReturn()) {
      window.history.replaceState(null, "", SETTINGS_RETURN_HASH);
    }
    renderSetup(await invoke("enter_settings"));
    elements.message.textContent = "Voice listening is stopped while Settings is open.";
  } catch (error) {
    elements.detail.textContent = friendlyError(error);
  }
}

function renderRuntime(snapshot) {
  elements.onboarding.hidden = true;
  elements.runtime.hidden = false;
  const ready = snapshot.state === "ready";
  elements.dot.dataset.ready = String(ready);
  elements.title.textContent = ready ? "Voice runtime ready" : "Voice runtime unavailable";
  elements.detail.textContent = snapshot.detail;
  elements.protocol.textContent = `v${snapshot.protocol_version}`;
  elements.session.textContent = snapshot.session_id || "—";
  elements.appSupport.textContent = snapshot.app_support_dir || "—";
  if (ready && snapshot.control_url) {
    const endpoint = new URL(snapshot.control_url);
    if (endpoint.protocol !== "http:" || endpoint.hostname !== "127.0.0.1") {
      throw new Error("Sidecar returned an invalid control endpoint.");
    }
    window.history.replaceState(null, "", SETTINGS_RETURN_HASH);
    window.location.assign(endpoint.href);
  }
}

async function load() {
  if (!invoke) {
    elements.message.textContent = "Open this page through the Hey Jarvis desktop app.";
    return;
  }
  try {
    const settingsMode = isSettingsReturn();
    const snapshot = await invoke(settingsMode ? "enter_settings" : "onboarding_status");
    renderSetup(snapshot);
    if (settingsMode) {
      elements.message.textContent = "Voice listening is stopped while Settings is open.";
    }
    if (!settingsMode && snapshot.completed && snapshot.openai_configured) {
      renderRuntime(await invoke("sidecar_status"));
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
    if (String(error).includes("credential_prompt_cancelled")) {
      elements.message.textContent = "No changes were made.";
    } else {
      elements.message.textContent = friendlyError(error);
    }
  }
}

async function deleteCredential(kind) {
  try {
    await invoke("delete_credential", { kind });
    renderSetup(await invoke("onboarding_status"));
    elements.message.textContent = "Removed from macOS Keychain.";
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

async function checkMicrophoneAndStart() {
  if (!setup?.openai_configured) return;
  elements.message.textContent = "Checking the built-in microphone…";
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (error) {
    if (error?.name === "NotAllowedError" || error?.name === "SecurityError") {
      renderSetup(await invoke("record_microphone_denied"));
      elements.message.textContent = "Microphone access is required, but listening remains off. Enable it in System Settings and retry.";
    } else if (error?.name === "NotFoundError") {
      elements.message.textContent = "No microphone was found. Connect or enable an input device, then retry.";
    } else {
      elements.message.textContent = "The microphone check failed and listening remains off. Check the input device and retry.";
    }
    return;
  }

  for (const track of stream.getTracks()) track.stop();
  elements.microphoneStatus.textContent = "Microphone access granted; the temporary check stream was released.";
  elements.message.textContent = "Microphone access is ready. Starting the local voice runtime…";
  try {
    renderRuntime(await invoke("complete_onboarding"));
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
}

elements.saveOpenai.addEventListener("click", () => saveCredential("openai"));
elements.saveFinnhub.addEventListener("click", () => saveCredential("finnhub"));
elements.deleteOpenai.addEventListener("click", () => deleteCredential("openai"));
elements.deleteFinnhub.addEventListener("click", () => deleteCredential("finnhub"));
elements.start.addEventListener("click", checkMicrophoneAndStart);
elements.microphoneSettings.addEventListener("click", async () => {
  try {
    await invoke("open_microphone_settings");
  } catch (error) {
    elements.message.textContent = friendlyError(error);
  }
});
elements.health.addEventListener("click", async () => {
  try {
    renderRuntime(await invoke("sidecar_health"));
  } catch (error) {
    elements.detail.textContent = friendlyError(error);
  }
});
elements.restart.addEventListener("click", async () => {
  try {
    renderRuntime(await invoke("restart_sidecar"));
  } catch (error) {
    elements.detail.textContent = friendlyError(error);
  }
});
elements.runtimeSettings.addEventListener("click", showSettings);
window.addEventListener("pageshow", (event) => {
  if (event.persisted && isSettingsReturn()) showSettings();
});

load();

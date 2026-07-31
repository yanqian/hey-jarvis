"use strict";

const { invoke } = window.__TAURI__.core;
const AUDIO_CONSTRAINTS = {
  echoCancellation: { exact: true },
  noiseSuppression: true,
  autoGainControl: true,
  channelCount: 1,
};

let probe = null;
let peer = null;
let dataChannel = null;
let mediaStream = null;
let activeSession = false;
let assistantSpeaking = false;
let events = [];

const $ = (id) => document.getElementById(id);

function safeValue(value) {
  if (typeof value === "boolean" || typeof value === "number") return value;
  if (typeof value === "string" && /^[A-Za-z0-9_.:-]{1,100}$/.test(value)) return value;
  return null;
}

function log(type, detail = {}) {
  const safeDetail = {};
  for (const [key, value] of Object.entries(detail)) {
    const safe = safeValue(value);
    if (safe !== null) safeDetail[key] = safe;
  }
  events.push({ at_ms: Math.round(performance.now()), type, ...safeDetail });
  events = events.slice(-100);
  $("events").textContent = events.map((entry) => JSON.stringify(entry)).join("\n");
}

function setStatus(value) {
  $("status").textContent = value;
}

function setControls({ canStart = false, canLong = false, canStop = false } = {}) {
  $("start").disabled = !canStart;
  $("long").disabled = !canLong;
  $("stop").disabled = !canStop;
}

async function api(path, { method = "GET", body, contentType = "application/json" } = {}) {
  if (!probe) throw new Error("Python sidecar configuration is unavailable");
  const headers = { "X-Probe-Token": probe.token };
  if (body !== undefined) headers["Content-Type"] = contentType;
  const response = await fetch(`${probe.base_url}${path}`, { method, headers, body });
  if (!response.ok) {
    let message = `Probe request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.message || payload.error || message;
    } catch {}
    throw new Error(message);
  }
  return response;
}

async function jsonApi(path, payload = undefined) {
  const response = await api(path, {
    method: payload === undefined ? "GET" : "POST",
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  return response.json();
}

function renderSettings(settings) {
  const keys = [
    "echoCancellation",
    "echoCancellationRequested",
    "echoCancellationAllSupported",
    "noiseSuppression",
    "autoGainControl",
    "sampleRate",
    "channelCount",
  ];
  for (const key of keys) {
    const cell = document.querySelector(`[data-setting="${key}"]`);
    if (cell) cell.textContent = String(settings[key] ?? "not reported");
  }
}

async function preferStrongestEchoCancellation(track) {
  const capabilities = typeof track.getCapabilities === "function" ? track.getCapabilities() : {};
  const advertised = Array.isArray(capabilities.echoCancellation)
    ? capabilities.echoCancellation
    : [];
  const allSupported = advertised.includes("all");
  if (allSupported) {
    try {
      await track.applyConstraints({
        ...AUDIO_CONSTRAINTS,
        echoCancellation: { exact: "all" },
      });
      return { requested: "all", allSupported: true };
    } catch {}
  }
  await track.applyConstraints(AUDIO_CONSTRAINTS);
  return { requested: "true", allSupported };
}

async function reportEvent(type, detail = {}) {
  await jsonApi("/event", { type, ...detail });
  log(type, detail);
}

async function waitForSidecar() {
  probe = await invoke("probe_config");
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const health = await jsonApi("/health");
      $("sidecar").textContent = health.openai_configured
        ? "ready · OpenAI configured"
        : "ready · add OPENAI_API_KEY to spike .env";
      setStatus("Ready for isolated WKWebView trial");
      setControls({ canStart: health.openai_configured });
      log("sidecar_ready", { attempt });
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  throw new Error("Python sidecar did not become ready");
}

async function handleRealtimeEvent(event) {
  const tracked = new Set([
    "session.created",
    "input_audio_buffer.speech_started",
    "input_audio_buffer.speech_stopped",
    "response.created",
    "response.done",
    "output_audio_buffer.started",
    "output_audio_buffer.stopped",
    "error",
  ]);
  if (!tracked.has(event.type)) return;
  log(event.type, { status: event.response?.status });
  if (event.type === "session.created") {
    await reportEvent("session_created");
    setStatus("Live · speak naturally");
  }
  if (event.type === "input_audio_buffer.speech_started") {
    await reportEvent("speech_started", { during_playback: assistantSpeaking });
  }
  if (event.type === "input_audio_buffer.speech_stopped") {
    await reportEvent("speech_stopped");
  }
  if (event.type === "response.created") await reportEvent("response_created");
  if (event.type === "response.done") {
    await reportEvent("response_done", { status: String(event.response?.status || "unknown") });
  }
  if (event.type === "output_audio_buffer.started") {
    assistantSpeaking = true;
    await reportEvent("playback_started");
  }
  if (event.type === "output_audio_buffer.stopped") {
    assistantSpeaking = false;
    await reportEvent("playback_stopped");
  }
  if (event.type === "error") {
    await reportEvent("error", { reason: "realtime_error" });
    await stopSession("realtime_error");
  }
}

async function startSession() {
  if (activeSession) return;
  setControls();
  setStatus("Requesting WKWebView microphone");
  await reportEvent("microphone_requested");
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: AUDIO_CONSTRAINTS });
    const track = mediaStream.getAudioTracks()[0];
    if (!track) throw new Error("WKWebView returned no microphone track");
    const echoPreference = await preferStrongestEchoCancellation(track);
    const settings = track.getSettings();
    const capture = {
      echoCancellation: settings.echoCancellation,
      echoCancellationRequested: echoPreference.requested,
      echoCancellationAllSupported: echoPreference.allSupported,
      noiseSuppression: settings.noiseSuppression,
      autoGainControl: settings.autoGainControl,
      sampleRate: settings.sampleRate,
      channelCount: settings.channelCount,
    };
    renderSettings(capture);
    await reportEvent("microphone_acquired", capture);

    peer = new RTCPeerConnection();
    peer.addTrack(track, mediaStream);
    peer.ontrack = (event) => {
      $("remote-audio").srcObject = event.streams[0];
      log("remote_audio_track");
    };
    peer.onconnectionstatechange = () => {
      const state = peer?.connectionState || "closed";
      log("peer_state", { state });
      if (["failed", "closed"].includes(state) && activeSession) {
        stopSession(`peer_${state}`).catch(() => {});
      }
    };

    dataChannel = peer.createDataChannel("oai-events");
    dataChannel.onopen = async () => {
      activeSession = true;
      setStatus("Connected · waiting for session.created");
      setControls({ canLong: true, canStop: true });
      await reportEvent("transport_connected");
    };
    dataChannel.onmessage = (message) => {
      try {
        handleRealtimeEvent(JSON.parse(message.data)).catch(() => {});
      } catch {}
    };
    dataChannel.onclose = () => {
      if (activeSession) stopSession("data_channel_closed").catch(() => {});
    };

    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    const answer = await api("/session", {
      method: "POST",
      contentType: "application/sdp",
      body: offer.sdp,
    });
    await peer.setRemoteDescription({ type: "answer", sdp: await answer.text() });
    log("sdp_answer_applied");
  } catch (error) {
    log("start_failed", { reason: error.name || "start_error" });
    await stopSession("start_failed", { suppressReacquire: true });
    setStatus(`Start failed: ${error.message}`);
    setControls({ canStart: true });
  }
}

function requestLongAnswer() {
  if (!dataChannel || dataChannel.readyState !== "open") return;
  dataChannel.send(
    JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [
          {
            type: "input_text",
            text: "Count slowly from one to one hundred. Say every number clearly and do not abbreviate.",
          },
        ],
      },
    }),
  );
  dataChannel.send(JSON.stringify({ type: "response.create" }));
  log("long_answer_requested");
}

async function stopSession(reason = "user_stop", options = {}) {
  const hadMedia = Boolean(mediaStream);
  activeSession = false;
  assistantSpeaking = false;
  const channel = dataChannel;
  dataChannel = null;
  if (channel) {
    channel.onclose = null;
    try {
      channel.close();
    } catch {}
  }
  const activePeer = peer;
  peer = null;
  if (activePeer) {
    activePeer.onconnectionstatechange = null;
    try {
      activePeer.close();
    } catch {}
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  const audio = $("remote-audio");
  audio.pause();
  audio.srcObject = null;
  setControls();

  if (hadMedia) await reportEvent("media_released", { reason });
  if (!options.suppressReacquire) {
    setStatus("WebRTC stopped · probing Python microphone reacquisition");
    await new Promise((resolve) => setTimeout(resolve, 300));
    const result = await jsonApi("/reacquire", {});
    renderReacquire(result);
    await reportEvent("reacquire_result", { ok: result.ok, reason: result.reason });
  }
  setStatus("Stopped · ready for another trial");
  setControls({ canStart: true });
}

function renderReacquire(result) {
  $("reacquire").textContent = result.ok
    ? `PASS · ${result.frames} frames`
    : `FAIL · ${result.reason || "unknown"}`;
}

async function loadReport() {
  const report = await jsonApi("/report");
  $("report").textContent = JSON.stringify(report, null, 2);
}

window.addEventListener("DOMContentLoaded", () => {
  $("start").addEventListener("click", startSession);
  $("long").addEventListener("click", requestLongAnswer);
  $("stop").addEventListener("click", () => stopSession());
  $("refresh-report").addEventListener("click", loadReport);
  waitForSidecar().catch((error) => {
    setStatus(`Sidecar failed: ${error.message}`);
    log("sidecar_failed", { reason: "not_ready" });
  });
});

window.addEventListener("beforeunload", () => {
  if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop());
});

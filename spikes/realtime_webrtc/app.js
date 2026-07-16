"use strict";

const MAX_EVENTS = 200;
const REQUESTED_AUDIO_CONSTRAINTS = Object.freeze({
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
  channelCount: 1,
});
const SAFE_EVENT_TYPES = new Set([
  "session.created",
  "session.updated",
  "input_audio_buffer.speech_started",
  "input_audio_buffer.speech_stopped",
  "conversation.item.added",
  "response.created",
  "response.output_item.added",
  "response.output_audio.done",
  "response.done",
  "response.cancelled",
  "rate_limits.updated",
  "error",
]);

let peerConnection = null;
let dataChannel = null;
let localStream = null;
let sessionStartedAt = null;
let assistantSpeaking = false;
let firstAudioSeenForResponse = false;
let model = null;
let voice = null;
let actualSettings = {};
let events = [];
let counters = { speechStarted: 0, speechDuringAssistant: 0, cancelled: 0, errors: 0 };

const $ = (id) => document.getElementById(id);

function elapsedMs() {
  return sessionStartedAt === null ? 0 : Math.round(performance.now() - sessionStartedAt);
}

function setStatus(label, state) {
  $("status").textContent = label;
  $("status").dataset.state = state;
}

function safeText(value, maxLength = 180) {
  if (typeof value !== "string") return undefined;
  return value.replace(/\s+/g, " ").slice(0, maxLength);
}

function record(type, detail = {}) {
  const entry = { at_ms: elapsedMs(), type, ...detail };
  events.push(entry);
  if (events.length > MAX_EVENTS) events = events.slice(-MAX_EVENTS);
  $("events").textContent = events.map((event) => JSON.stringify(event)).join("\n");
  $("eventCount").textContent = `${events.length} events`;
  $("events").scrollTop = $("events").scrollHeight;
}

function sanitizeServerEvent(event) {
  const safe = {};
  if (event.response?.id) safe.response_id = safeText(event.response.id, 80);
  if (event.response?.status) safe.status = safeText(event.response.status, 40);
  if (event.item_id) safe.item_id = safeText(event.item_id, 80);
  if (event.item?.id) safe.item_id = safeText(event.item.id, 80);
  if (event.error?.code) safe.error_code = safeText(event.error.code, 80);
  if (event.error?.message) safe.error_message = safeText(event.error.message);
  return safe;
}

function handleServerEvent(raw) {
  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    counters.errors += 1;
    record("malformed_server_event");
    return;
  }
  const type = typeof event.type === "string" ? event.type : "unknown_event";

  if (type === "response.output_audio.delta") {
    if (!firstAudioSeenForResponse) {
      assistantSpeaking = true;
      firstAudioSeenForResponse = true;
      record("assistant_audio_started", { response_id: safeText(event.response_id, 80) });
    }
    return;
  }
  if (type === "input_audio_buffer.speech_started") {
    counters.speechStarted += 1;
    if (assistantSpeaking) counters.speechDuringAssistant += 1;
    record(type, { during_assistant_audio: assistantSpeaking });
    return;
  }
  if (type === "response.created") {
    firstAudioSeenForResponse = false;
  }
  if (type === "response.output_audio.done" || type === "response.done") {
    assistantSpeaking = false;
  }
  if (type === "response.cancelled" || event.response?.status === "cancelled") {
    counters.cancelled += 1;
    assistantSpeaking = false;
  }
  if (type === "error") counters.errors += 1;
  if (SAFE_EVENT_TYPES.has(type)) record(type, sanitizeServerEvent(event));
}

function renderSettings(settings) {
  const values = {
    echoCancellation: settings.echoCancellation,
    noiseSuppression: settings.noiseSuppression,
    autoGainControl: settings.autoGainControl,
    sampleRate: settings.sampleRate,
    channelCount: settings.channelCount,
    device: settings.deviceId ? "selected device (id redacted)" : "browser default",
  };
  $("settings").querySelectorAll("div").forEach((row) => {
    const key = row.querySelector("dt").textContent;
    const value = values[key];
    row.querySelector("dd").textContent = value === undefined ? "not reported" : String(value);
  });
}

async function startSession() {
  $("start").disabled = true;
  setStatus("Requesting temporary session…", "connecting");
  events = [];
  counters = { speechStarted: 0, speechDuringAssistant: 0, cancelled: 0, errors: 0 };
  sessionStartedAt = performance.now();
  record("probe_start_requested", { user_agent: safeText(navigator.userAgent, 140) });

  try {
    const tokenResponse = await fetch("/token", { method: "POST", cache: "no-store" });
    const tokenData = await tokenResponse.json();
    if (!tokenResponse.ok || !tokenData.value) {
      throw new Error(tokenData.message || `temporary session failed (${tokenResponse.status})`);
    }
    model = safeText(tokenData.model, 80);
    voice = safeText(tokenData.voice, 40);

    localStream = await navigator.mediaDevices.getUserMedia({
      audio: REQUESTED_AUDIO_CONSTRAINTS,
    });
    const microphoneTrack = localStream.getAudioTracks()[0];
    if (!microphoneTrack) throw new Error("browser returned no microphone track");
    actualSettings = microphoneTrack.getSettings();
    renderSettings(actualSettings);
    record("microphone_ready", {
      echoCancellation: actualSettings.echoCancellation,
      noiseSuppression: actualSettings.noiseSuppression,
      autoGainControl: actualSettings.autoGainControl,
      sampleRate: actualSettings.sampleRate,
      channelCount: actualSettings.channelCount,
    });

    peerConnection = new RTCPeerConnection();
    peerConnection.onconnectionstatechange = () => {
      record("peer_connection_state", { state: peerConnection?.connectionState || "closed" });
      if (peerConnection?.connectionState === "connected") setStatus("Live · speak naturally", "live");
    };
    peerConnection.ontrack = (event) => {
      $("remoteAudio").srcObject = event.streams[0];
      record("remote_audio_track", { kind: event.track.kind });
    };
    peerConnection.addTrack(microphoneTrack, localStream);

    dataChannel = peerConnection.createDataChannel("oai-events");
    dataChannel.addEventListener("open", () => {
      $("longAnswer").disabled = false;
      record("data_channel_open");
    });
    dataChannel.addEventListener("close", () => record("data_channel_close"));
    dataChannel.addEventListener("message", (event) => handleServerEvent(event.data));

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    const sdpResponse = await fetch("https://api.openai.com/v1/realtime/calls", {
      method: "POST",
      body: offer.sdp,
      headers: {
        Authorization: `Bearer ${tokenData.value}`,
        "Content-Type": "application/sdp",
      },
    });
    if (!sdpResponse.ok) throw new Error(`Realtime WebRTC negotiation failed (${sdpResponse.status})`);
    await peerConnection.setRemoteDescription({ type: "answer", sdp: await sdpResponse.text() });
    record("webrtc_answer_applied", { model, voice });
    $("stop").disabled = false;
  } catch (error) {
    counters.errors += 1;
    record("probe_start_failed", { message: safeText(error?.message || String(error)) });
    setStatus("Failed · inspect evidence", "error");
    await stopSession(false);
  }
}

async function stopSession(recordStop = true) {
  if (recordStop) record("probe_stop_requested");
  if (dataChannel) {
    try { dataChannel.close(); } catch {}
    dataChannel = null;
  }
  if (peerConnection) {
    try { peerConnection.close(); } catch {}
    peerConnection = null;
  }
  if (localStream) {
    localStream.getTracks().forEach((track) => track.stop());
    localStream = null;
  }
  const audio = $("remoteAudio");
  audio.pause();
  audio.srcObject = null;
  assistantSpeaking = false;
  firstAudioSeenForResponse = false;
  $("start").disabled = false;
  $("longAnswer").disabled = true;
  $("stop").disabled = true;
  if (recordStop) setStatus("Stopped", "idle");
}

function buildReport() {
  return {
    probe: "hey-jarvis-realtime-webrtc-speakerphone",
    generated_at: new Date().toISOString(),
    model,
    voice,
    requested_audio_constraints: REQUESTED_AUDIO_CONSTRAINTS,
    actual_audio_settings: {
      echoCancellation: actualSettings.echoCancellation,
      noiseSuppression: actualSettings.noiseSuppression,
      autoGainControl: actualSettings.autoGainControl,
      sampleRate: actualSettings.sampleRate,
      channelCount: actualSettings.channelCount,
    },
    counters,
    observations: {
      self_echo_false_interruption: $("selfEcho").value,
      user_barge_in_detected: $("bargeIn").value,
      old_response_stopped_promptly: $("oldStopped").value,
      notes: safeText($("notes").value, 1000) || "",
    },
    events,
  };
}

async function copyReport() {
  const report = JSON.stringify(buildReport(), null, 2);
  try {
    await navigator.clipboard.writeText(report);
    record("report_copied", { event_count: events.length });
  } catch {
    window.prompt("Copy validation report", report);
  }
}

function playLongTestAnswer() {
  if (!dataChannel || dataChannel.readyState !== "open") {
    record("long_test_answer_unavailable");
    return;
  }
  dataChannel.send(JSON.stringify({
    type: "conversation.item.create",
    item: {
      type: "message",
      role: "user",
      content: [{
        type: "input_text",
        text: "Count slowly from one to twenty. Say each number clearly and do not skip any numbers.",
      }],
    },
  }));
  dataChannel.send(JSON.stringify({ type: "response.create" }));
  record("long_test_answer_requested");
}

$("start").addEventListener("click", startSession);
$("longAnswer").addEventListener("click", playLongTestAnswer);
$("stop").addEventListener("click", () => stopSession(true));
$("copy").addEventListener("click", copyReport);
window.addEventListener("beforeunload", () => stopSession(false));

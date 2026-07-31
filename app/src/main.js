const invoke = window.__TAURI__?.core?.invoke;

const elements = {
  dot: document.querySelector("#status-dot"),
  title: document.querySelector("#status-title"),
  detail: document.querySelector("#status-detail"),
  protocol: document.querySelector("#protocol"),
  session: document.querySelector("#session"),
  appSupport: document.querySelector("#app-support"),
  health: document.querySelector("#health-check"),
  restart: document.querySelector("#restart"),
};

function render(snapshot) {
  const ready = snapshot.state === "ready";
  elements.dot.dataset.ready = String(ready);
  elements.title.textContent = ready ? "Sidecar ready" : "Sidecar unavailable";
  elements.detail.textContent = snapshot.detail;
  elements.protocol.textContent = `v${snapshot.protocol_version}`;
  elements.session.textContent = snapshot.session_id || "—";
  elements.appSupport.textContent = snapshot.app_support_dir || "—";
}

async function refresh(command = "sidecar_status") {
  if (!invoke) {
    render({
      state: "unavailable",
      detail: "Open this page through the Hey Jarvis desktop app.",
      protocol_version: 1,
      session_id: "",
      app_support_dir: "",
    });
    return;
  }

  try {
    render(await invoke(command));
  } catch (error) {
    render({
      state: "error",
      detail: String(error),
      protocol_version: 1,
      session_id: "",
      app_support_dir: "",
    });
  }
}

elements.health.addEventListener("click", () => refresh("sidecar_health"));
elements.restart.addEventListener("click", () => refresh("restart_sidecar"));
refresh();

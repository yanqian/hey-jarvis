export class StartupRuntimeTimeout extends Error {
  constructor() {
    super("startup_runtime_timed_out");
    this.name = "StartupRuntimeTimeout";
  }
}

function delay(milliseconds) {
  return new Promise(resolve => globalThis.setTimeout(resolve, milliseconds));
}

function beforeDeadline(promise, milliseconds) {
  if (milliseconds <= 0) return Promise.reject(new StartupRuntimeTimeout());
  let timeoutId;
  const timeout = new Promise((_, reject) => {
    timeoutId = globalThis.setTimeout(
      () => reject(new StartupRuntimeTimeout()),
      milliseconds,
    );
  });
  return Promise.race([promise, timeout]).finally(() => globalThis.clearTimeout(timeoutId));
}

export async function completeStartupRuntime({
  invoke,
  navigate,
  smartSpeakerMode = false,
  timeoutMs = 30000,
  pollIntervalMs = 100,
  now = Date.now,
  sleep = delay,
}) {
  const deadline = now() + timeoutMs;
  const invokeBeforeDeadline = command => beforeDeadline(
    Promise.resolve().then(() => invoke(command)),
    deadline - now(),
  );

  while (await invokeBeforeDeadline("startup_runtime_pending")) {
    const remaining = deadline - now();
    if (remaining <= 0) throw new StartupRuntimeTimeout();
    await sleep(Math.min(pollIntervalMs, remaining));
  }

  const runtime = await invokeBeforeDeadline("sidecar_status");
  if (runtime.state !== "ready") return { status: "failed", runtime };

  navigate(runtime, { smartSpeakerMode: smartSpeakerMode === true });
  return { status: "navigated", runtime };
}

export async function runStartupHandoff({ onTimeout, onFailure, ...options }) {
  try {
    const outcome = await completeStartupRuntime(options);
    if (outcome.status === "failed") onFailure(outcome.runtime?.detail);
    return outcome;
  } catch (error) {
    if (error instanceof StartupRuntimeTimeout) {
      onTimeout();
      return { status: "timeout", error };
    }
    onFailure(error);
    return { status: "failed", error };
  }
}

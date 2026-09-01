import assert from "node:assert/strict";
import test from "node:test";

import {
  completeStartupRuntime,
  runStartupHandoff,
  StartupRuntimeTimeout,
} from "../src/startup-runtime.js";

function readySnapshot() {
  return {
    state: "ready",
    control_url: "http://127.0.0.1:49152/?lease=test",
    session_id: "session-test",
  };
}

test("pending-to-ready handoff carries enabled Smart Speaker Mode explicitly", async () => {
  const pending = [true, false];
  const calls = [];
  let navigation;
  const outcome = await completeStartupRuntime({
    invoke: async command => {
      calls.push(command);
      return command === "startup_runtime_pending" ? pending.shift() : readySnapshot();
    },
    navigate: (runtime, options) => { navigation = { runtime, options }; },
    smartSpeakerMode: true,
    sleep: async () => {},
  });

  assert.equal(outcome.status, "navigated");
  assert.deepEqual(calls, [
    "startup_runtime_pending",
    "startup_runtime_pending",
    "sidecar_status",
  ]);
  assert.equal(navigation.runtime.session_id, "session-test");
  assert.deepEqual(navigation.options, { smartSpeakerMode: true });
});

test("ready handoff keeps disabled Smart Speaker Mode fragment-free", async () => {
  let options;
  await completeStartupRuntime({
    invoke: async command => command === "startup_runtime_pending" ? false : readySnapshot(),
    navigate: (_runtime, value) => { options = value; },
    smartSpeakerMode: false,
  });
  assert.deepEqual(options, { smartSpeakerMode: false });
});

test("non-ready runtime fails closed without navigation", async () => {
  let navigated = false;
  const outcome = await completeStartupRuntime({
    invoke: async command => command === "startup_runtime_pending"
      ? false
      : { state: "error", detail: "wake model failed" },
    navigate: () => { navigated = true; },
  });
  assert.equal(outcome.status, "failed");
  assert.equal(outcome.runtime.detail, "wake model failed");
  assert.equal(navigated, false);
});

test("rejected handoff reports failure on the visible startup callback", async () => {
  let visibleFailure;
  const outcome = await runStartupHandoff({
    invoke: async () => { throw new Error("ipc rejected"); },
    navigate: () => assert.fail("navigation must not run"),
    onTimeout: () => assert.fail("rejection is not a timeout"),
    onFailure: error => { visibleFailure = String(error); },
  });
  assert.equal(outcome.status, "failed");
  assert.match(visibleFailure, /ipc rejected/);
});

test("never-settling IPC cannot suppress the overall startup deadline", async () => {
  await assert.rejects(
    completeStartupRuntime({
      invoke: () => new Promise(() => {}),
      navigate: () => assert.fail("navigation must not run"),
      timeoutMs: 15,
    }),
    StartupRuntimeTimeout,
  );
});

test("navigation exception is converted to a visible startup failure", async () => {
  let visibleFailure;
  const outcome = await runStartupHandoff({
    invoke: async command => command === "startup_runtime_pending" ? false : readySnapshot(),
    navigate: () => { throw new ReferenceError("route is not defined"); },
    smartSpeakerMode: true,
    onTimeout: () => assert.fail("navigation exception is not a timeout"),
    onFailure: error => { visibleFailure = String(error); },
  });
  assert.equal(outcome.status, "failed");
  assert.match(visibleFailure, /route is not defined/);
});

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(
  new URL("../../src/realtime_host/static/negotiation-diagnostics.js", import.meta.url),
  "utf8",
);
const context = {};
vm.runInNewContext(source, context);
const { buildNegotiationDiagnostic } = context.HeyJarvisNegotiationDiagnostics;

test("distinguishes loopback and upstream negotiation statuses", () => {
  const result = buildNegotiationDiagnostic(409, {
    error: {
      type: "realtime_call_failed",
      upstream_http_status: 400,
      provider_error_type: "invalid_request_error",
      provider_error_code: "unsupported_value",
      message: "private provider message",
      request_id: "req_private",
    },
  });
  assert.deepEqual({ ...result }, {
    reason: "webrtc_negotiation_failed",
    localHttpStatus: 409,
    upstreamHttpStatus: 400,
    errorType: "invalid_request_error",
    errorCode: "unsupported_value",
  });
});

test("drops missing malformed and unbounded provider details", () => {
  for (const payload of [
    null,
    { error: "host_control_failed", message: "private" },
    {
      error: {
        upstream_http_status: 200,
        provider_error_type: "unsafe value",
        provider_error_code: "x".repeat(101),
      },
    },
  ]) {
    assert.deepEqual({ ...buildNegotiationDiagnostic(409, payload) }, {
      reason: "webrtc_negotiation_failed",
      localHttpStatus: 409,
    });
  }
});

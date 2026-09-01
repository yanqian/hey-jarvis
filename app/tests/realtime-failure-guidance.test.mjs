import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(
  new URL("../../src/realtime_host/static/failure-guidance.js", import.meta.url),
  "utf8",
);
const context = {};
vm.runInNewContext(source, context);
const { guidance, preserveDuringAvailability } = context.HeyJarvisFailureGuidance;

const diagnostic = (overrides = {}) => ({
  reason: "webrtc_negotiation_failed",
  localHttpStatus: 409,
  ...overrides,
});

test("maps known failures to fixed bilingual actionable guidance", () => {
  const cases = [
    [{ upstreamHttpStatus: 429, errorType: "insufficient_quota", errorCode: "credit_balance_exhausted" }, "quota"],
    [{ upstreamHttpStatus: 401, errorCode: "invalid_api_key" }, "auth"],
    [{ upstreamHttpStatus: 403 }, "access"],
    [{ upstreamHttpStatus: 429 }, "rate"],
    [{ upstreamHttpStatus: 503 }, "service"],
  ];
  for (const [fields, category] of cases) {
    const english = guidance("en", diagnostic(fields));
    const chinese = guidance("zh-CN", diagnostic(fields));
    assert.equal(english.category, category);
    assert.equal(chinese.category, category);
    assert.notEqual(english.title, chinese.title);
    assert.notEqual(english.detail, chinese.detail);
  }
  const quota = guidance("en", diagnostic({ upstreamHttpStatus: 429, errorCode: "credit_balance_exhausted" }));
  assert.equal(quota.category, "quota", "quota must take precedence over generic 429 guidance");
  assert.match(quota.detail, /API Platform Billing/);
});

test("unknown or hostile fields never reach the fixed presentation", () => {
  const hostile = "sk-private-provider-message";
  for (const value of [
    null,
    {},
    diagnostic({ upstreamHttpStatus: 418 }),
    diagnostic({ errorType: hostile, errorCode: hostile, message: hostile }),
  ]) assert.equal(guidance("en", value), null);
  const known = guidance("en", diagnostic({ upstreamHttpStatus: 503, message: hostile, requestId: hostile }));
  assert.equal(known.category, "service");
  assert.equal(JSON.stringify(known).includes(hostile), false);
});

test("keeps a recovered-wake failure visible only until the next active flow", () => {
  const quota = diagnostic({ upstreamHttpStatus: 429, errorCode: "credit_balance_exhausted" });
  assert.equal(preserveDuringAvailability("error", "wake_listening", true, false, quota), true);
  assert.equal(preserveDuringAvailability("error", "wake_listening", true, false, diagnostic({ upstreamHttpStatus: 418 })), false);
  assert.equal(preserveDuringAvailability("connecting", "wake_listening", true, false, quota), false);
  assert.equal(preserveDuringAvailability("error", "ready", true, false, quota), false);
  assert.equal(preserveDuringAvailability("error", "wake_listening", true, true, quota), false);
});

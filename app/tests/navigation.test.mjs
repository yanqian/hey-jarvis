import assert from "node:assert/strict";
import test from "node:test";

import { assistantModeFragment } from "../src/navigation.js";

test("fast returning startup preserves enabled Smart Speaker Mode", () => {
  assert.equal(
    assistantModeFragment({ smartSpeakerMode: true }),
    "smart-speaker-mode",
  );
});

test("fast returning startup omits Smart Speaker Mode when disabled", () => {
  assert.equal(assistantModeFragment({ smartSpeakerMode: false }), "");
  assert.equal(assistantModeFragment(), "");
});

test("sleep recovery keeps resume precedence", () => {
  assert.equal(
    assistantModeFragment({ recovery: true, smartSpeakerMode: true }),
    "smart-speaker-resume",
  );
});

import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync } from "node:fs";

test("generated web client exists", () => {
  assert.equal(existsSync(new URL("../generated/web-client/index.ts", import.meta.url)), true);
});

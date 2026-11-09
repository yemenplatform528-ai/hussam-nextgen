import test from "node:test";
import assert from "node:assert/strict";
import { Readable } from "node:stream";
import { readRequestBody } from "../body-reader.js";

test("preserves UTF-8 characters split across request chunks", async () => {
  const json = JSON.stringify({ message: "مرحبا" });
  const bytes = Buffer.from(json, "utf8");
  const arabicCharacter = Buffer.from("م", "utf8");
  const splitAt = bytes.indexOf(arabicCharacter) + 1;
  assert.ok(splitAt > 0, "test payload contains the Arabic character");
  const raw = await readRequestBody(
    Readable.from([bytes.subarray(0, splitAt), bytes.subarray(splitAt)]),
    1024
  );
  assert.equal(raw, json);
  assert.equal(JSON.parse(raw).message, "مرحبا");
});

test("enforces request size in bytes", async () => {
  await assert.rejects(
    readRequestBody(Readable.from([Buffer.from("12345", "utf8")]), 4),
    (error) => error.code === "REQUEST_TOO_LARGE"
  );
});

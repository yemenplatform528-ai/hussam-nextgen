import test from "node:test";
import assert from "node:assert/strict";
import { createRateLimiter } from "../rate-limiter.js";

test("rate limiter fails closed at capacity without resetting live client counters", () => {
  const limiter = createRateLimiter({ maxBuckets: 3 });
  assert.equal(limiter.allow("client-a", 2, 60_000), true);
  assert.equal(limiter.allow("client-b", 2, 60_000), true);
  assert.equal(limiter.allow("client-c", 2, 60_000), true);
  assert.equal(limiter.allow("client-a", 2, 60_000), true);
  assert.equal(limiter.size(), 3);

  assert.equal(limiter.allow("client-d", 2, 60_000), false, "new clients must fail closed while all buckets are live");
  assert.equal(limiter.size(), 3, "bucket map must remain bounded");
  assert.equal(limiter.allow("client-a", 2, 60_000), false, "a recent client's counter must not be reset by key churn");
  assert.equal(limiter.size(), 3);
});

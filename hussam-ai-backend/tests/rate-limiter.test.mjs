import test from "node:test";
import assert from "node:assert/strict";
import { createRateLimiter } from "../../rate-limiter.js";

test("rate limiter keeps a hard bucket bound and preserves recently used counters", () => {
  const limiter = createRateLimiter({ maxBuckets: 3 });
  assert.equal(limiter.allow("client-a", 2, 60_000), true);
  assert.equal(limiter.allow("client-b", 2, 60_000), true);
  assert.equal(limiter.allow("client-c", 2, 60_000), true);
  assert.equal(limiter.allow("client-a", 2, 60_000), true);
  assert.equal(limiter.size(), 3);
  assert.equal(limiter.allow("client-d", 2, 60_000), true);
  assert.equal(limiter.size(), 3, "new clients must not grow the bucket map beyond capacity");
  assert.equal(limiter.allow("client-a", 2, 60_000), false, "a recent client's counter must survive eviction of older buckets");
  assert.equal(limiter.size(), 3);
});

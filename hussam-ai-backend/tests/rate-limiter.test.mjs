import test from "node:test";
import assert from "node:assert/strict";
import { createRateLimiter } from "../rate-limiter.js";

test("rate limiter stays bounded and evicts least-recently-used keys instead of locking out new clients", () => {
  const limiter = createRateLimiter({ maxBuckets: 3 });
  assert.equal(limiter.allow("client-a", 3, 60_000), true);
  assert.equal(limiter.allow("client-b", 3, 60_000), true);
  assert.equal(limiter.allow("client-c", 3, 60_000), true);

  // Touch A so B becomes the least-recently-used bucket.
  assert.equal(limiter.allow("client-a", 3, 60_000), true);
  assert.equal(limiter.size(), 3);

  // Key churn must not turn the bounded map into a global login lockout.
  assert.equal(limiter.allow("client-d", 3, 60_000), true);
  assert.equal(limiter.size(), 3);

  // A retained bucket preserves its counter; the evicted key starts a fresh
  // best-effort bucket, which is why trusted edge throttling remains mandatory.
  assert.equal(limiter.allow("client-a", 3, 60_000), true);
  assert.equal(limiter.allow("client-a", 3, 60_000), false);
  assert.equal(limiter.allow("client-b", 3, 60_000), true);
  assert.equal(limiter.size(), 3);
});

export function createRateLimiter({ maxBuckets = 512 } = {}) {
  const capacity = Number.isInteger(maxBuckets) && maxBuckets > 0 ? maxBuckets : 512;
  const buckets = new Map();
  return {
    allow(key, limit, windowMs) {
      const now = Date.now();
      for (const [candidate, bucket] of buckets) if (now >= bucket.resetAt) buckets.delete(candidate);
      let bucket = buckets.get(key);
      if (!bucket) {
        // This in-process limiter is best-effort only. Evict the least-recently
        // used key rather than globally rejecting new clients at capacity: an
        // unauthenticated caller can rotate untrusted forwarded-IP headers and
        // otherwise fill the map to lock every legitimate client out.
        if (buckets.size >= capacity) buckets.delete(buckets.keys().next().value);
        bucket = { count: 0, resetAt: now + windowMs };
      } else if (now >= bucket.resetAt) {
        bucket = { count: 0, resetAt: now + windowMs };
      }
      if (bucket.count >= limit) {
        buckets.delete(key);
        buckets.set(key, bucket);
        return false;
      }
      bucket.count += 1;
      buckets.delete(key);
      buckets.set(key, bucket);
      return true;
    },
    size() { return buckets.size; }
  };
}

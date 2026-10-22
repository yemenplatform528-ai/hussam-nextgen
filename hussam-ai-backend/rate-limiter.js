export function createRateLimiter({ maxBuckets = 512 } = {}) {
  const capacity = Number.isInteger(maxBuckets) && maxBuckets > 0 ? maxBuckets : 512;
  const buckets = new Map();
  return {
    allow(key, limit, windowMs) {
      const now = Date.now();
      for (const [candidate, bucket] of buckets) if (now >= bucket.resetAt) buckets.delete(candidate);
      let bucket = buckets.get(key);
      if (!bucket) {
        // Never evict an unexpired counter: under key churn that would reset a
        // caller's throttle window. Fail closed for new keys until a bucket expires.
        if (buckets.size >= capacity) return false;
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

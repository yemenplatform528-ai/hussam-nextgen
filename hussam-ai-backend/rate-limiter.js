export function createRateLimiter({ maxBuckets = 512 } = {}) {
  const capacity = Number.isInteger(maxBuckets) && maxBuckets > 0 ? maxBuckets : 512;
  const buckets = new Map();
  return {
    allow(key, limit, windowMs) {
      const now = Date.now();
      for (const [candidate, bucket] of buckets) if (now >= bucket.resetAt) buckets.delete(candidate);
      let bucket = buckets.get(key);
      if (!bucket || now >= bucket.resetAt) bucket = { count: 0, resetAt: now + windowMs };
      if (bucket.count >= limit) {
        buckets.delete(key);
        buckets.set(key, bucket);
        return false;
      }
      bucket.count += 1;
      buckets.delete(key);
      buckets.set(key, bucket);
      while (buckets.size > capacity) buckets.delete(buckets.keys().next().value);
      return true;
    },
    size() { return buckets.size; }
  };
}

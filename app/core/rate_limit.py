"""Process-local and Redis-backed distributed API rate limiting."""
from __future__ import annotations
from threading import Lock
from time import monotonic

class RateLimiter:
    def __init__(self, limit: int = 600, window_seconds: int = 60):
        self.limit = max(1, int(limit)); self.window_seconds = max(1, int(window_seconds))
        self._lock = Lock(); self._buckets: dict[str, tuple[float, int]] = {}

    def check(self, key: str) -> tuple[bool, int, int]:
        now = monotonic()
        with self._lock:
            start, count = self._buckets.get(key, (now, 0))
            if now - start >= self.window_seconds: start, count = now, 0
            count += 1; self._buckets[key] = (start, count)
            remaining = max(0, self.limit - count)
            retry_after = max(1, int(self.window_seconds - (now - start)))
            return count <= self.limit, remaining, retry_after

    def reset(self) -> None:
        with self._lock: self._buckets.clear()

class RedisRateLimiter:
    """Atomic fixed-window limiter shared by all application instances."""
    def __init__(self, redis_url: str, limit: int = 600, window_seconds: int = 60, *, prefix: str = "hussam:rl"):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis rate limiting requires the redis package") from exc
        self.client = redis.Redis.from_url(redis_url, decode_responses=False)
        self.limit = max(1, int(limit)); self.window_seconds = max(1, int(window_seconds)); self.prefix = prefix
        self._script = self.client.register_script("""
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
            local ttl = redis.call('TTL', KEYS[1])
            return {count, ttl}
        """)

    def check(self, key: str) -> tuple[bool, int, int]:
        result = self._script(keys=[f"{self.prefix}:{key}"], args=[self.window_seconds])
        count, ttl = int(result[0]), max(1, int(result[1]))
        return count <= self.limit, max(0, self.limit - count), ttl

    def reset(self) -> None:
        # Administrative/test helper; production does not rely on it.
        return None

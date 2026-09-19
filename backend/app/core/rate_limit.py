"""Tiny in-memory sliding-window limiter for auth endpoints.

Per-process only: fine for one uvicorn worker. With several workers or
instances, back this with Redis instead.
"""
import threading
import time
from collections import defaultdict, deque

from app.core.errors import api_error


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def ensure_allowed(self, key: str) -> None:
        with self._lock:
            q = self._prune(key, time.monotonic())
            if len(q) >= self.limit:
                raise api_error(429, "RATE_LIMITED", "Too many attempts. Please wait a few minutes and try again.")

    def record(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset_all(self) -> None:
        with self._lock:
            self._hits.clear()


# 5 failed logins per email+IP per 5 minutes; 10 registrations per IP per hour.
login_limiter = SlidingWindowLimiter(limit=5, window_seconds=300)
register_limiter = SlidingWindowLimiter(limit=10, window_seconds=3600)

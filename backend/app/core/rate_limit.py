from collections import defaultdict, deque
from threading import Lock
import time

from app.core.errors import ApiError


class RateLimiter:
    """本机单进程限流；部署多进程时应接统一缓存，不能各进程独立计数。"""
    def __init__(self):
        self.entries = defaultdict(deque)
        self.lock = Lock()
        self.last_cleanup = 0.0

    def check(self, key, limit, window=60):
        now = time.monotonic()
        with self.lock:
            if now-self.last_cleanup > 60:
                for old_key in list(self.entries):
                    if not self.entries[old_key] or self.entries[old_key][-1] <= now-window:
                        del self.entries[old_key]
                self.last_cleanup = now
            values = self.entries[key]
            while values and values[0] <= now-window:
                values.popleft()
            if len(values) >= limit:
                raise ApiError(42901, "请求过于频繁，请稍后重试", 429)
            values.append(now)

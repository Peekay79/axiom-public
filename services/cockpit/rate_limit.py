import time


class RateLimiter:
    def __init__(self, min_interval_sec: int):
        self.min_interval = int(min_interval_sec)
        self.last = 0.0

    def allow(self) -> bool:
        now = time.time()
        if now - self.last >= self.min_interval:
            self.last = now
            return True
        return False


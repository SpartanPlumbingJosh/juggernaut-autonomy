import asyncio
import time
from collections import deque

class RateLimiter:
    """Rate limiter for API calls"""
    def __init__(self, max_requests: int = 60, period: float = 60.0):
        self.max_requests = max_requests
        self.period = period
        self.timestamps = deque(maxlen=max_requests)
        self.lock = asyncio.Lock()

    async def wait(self):
        """Wait until we can make another request"""
        async with self.lock:
            now = time.time()
            while len(self.timestamps) >= self.max_requests:
                oldest = self.timestamps[0]
                if now - oldest < self.period:
                    sleep_time = self.period - (now - oldest)
                    await asyncio.sleep(sleep_time)
                    now = time.time()
                else:
                    break
            
            if len(self.timestamps) >= self.max_requests:
                self.timestamps.popleft()
            
            self.timestamps.append(now)

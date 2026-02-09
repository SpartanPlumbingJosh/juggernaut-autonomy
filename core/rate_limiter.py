from collections import defaultdict
import time
from core.logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """Simple rate limiter implementation"""
    
    def __init__(self, max_requests: int = 100, period: int = 60):
        self.max_requests = max_requests
        self.period = period
        self.request_counts = defaultdict(list)
        
    def allow_request(self, client_id: str) -> bool:
        """Check if request is allowed"""
        current_time = time.time()
        timestamps = self.request_counts[client_id]
        
        # Remove old timestamps
        timestamps = [ts for ts in timestamps if current_time - ts < self.period]
        
        if len(timestamps) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {client_id}")
            return False
            
        timestamps.append(current_time)
        self.request_counts[client_id] = timestamps
        return True

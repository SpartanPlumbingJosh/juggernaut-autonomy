import time
import random
from typing import Callable, Dict, Any

from core.logging import log_action

class SelfHealingMiddleware:
    """Middleware for automatic error recovery."""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 0.3):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        
    def __call__(self, func: Callable) -> Callable:
        def wrapped(*args, **kwargs) -> Dict[str, Any]:
            retry_count = 0
            last_error = None
            
            while retry_count <= self.max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    retry_count += 1
                    if retry_count <= self.max_retries:
                        sleep_time = self._calculate_backoff(retry_count)
                        log_action("error.retry_attempt",
                                 f"Attempt {retry_count} failed, retrying in {sleep_time}s",
                                 level="warning", 
                                 error_data={"error": str(e)})
                        time.sleep(sleep_time)
            
            log_action("error.failure",
                      f"Operation failed after {self.max_retries} attempts",
                      level="error",
                      error_data={"error": str(last_error)})
            return {
                "success": False,
                "error": str(last_error),
                "retries": retry_count - 1
            }
            
        return wrapped

    def _calculate_backoff(self, retry_count: int) -> float:
        """Calculate exponential backoff with jitter."""
        jitter = random.uniform(0, 0.1)
        return (2 ** retry_count) * self.backoff_factor + jitter

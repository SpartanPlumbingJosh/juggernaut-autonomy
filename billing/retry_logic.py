import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

class RetryManager:
    def __init__(self):
        self.max_retries = 3
        self.retry_intervals = [timedelta(hours=1), timedelta(days=1), timedelta(days=3)]

    async def execute_with_retries(self, 
                                 operation: Callable,
                                 *args,
                                 **kwargs) -> Optional[Decimal]:
        """Execute an operation with retry logic"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = await operation(*args, **kwargs)
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < len(self.retry_intervals):
                    await asyncio.sleep(self.retry_intervals[attempt].total_seconds())
                else:
                    break
                    
        logger.error(f"Operation failed after {self.max_retries} attempts")
        raise last_error or Exception("Payment processing failed")

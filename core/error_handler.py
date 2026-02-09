"""
Error Handling - Manages system errors and alerts.
"""

import asyncio
import logging
import traceback
from typing import Optional

from core.notifications import send_alert

class ErrorHandler:
    """Handles system errors and notifications."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def handle_errors(self, error: Exception) -> bool:
        """Process and log system errors."""
        try:
            error_details = {
                "message": str(error),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.logger.error(f"System error: {error_details['message']}")
            
            # Log error to database
            await self._log_error_to_db(error_details)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling failed: {str(e)}")
            return False
            
    async def notify_alert(self, message: str) -> bool:
        """Send critical system alerts."""
        try:
            await send_alert(message)
            return True
        except Exception as e:
            self.logger.error(f"Failed to send alert: {str(e)}")
            return False
            
    async def _log_error_to_db(self, error_details: Dict) -> bool:
        """Log error details to database."""
        # Implementation would depend on your database setup
        return True

async def handle_errors(error: Exception) -> bool:
    """Public interface for error handling."""
    handler = ErrorHandler()
    return await handler.handle_errors(error)

async def notify_alert(message: str) -> bool:
    """Public interface for sending alerts."""
    handler = ErrorHandler()
    return await handler.notify_alert(message)

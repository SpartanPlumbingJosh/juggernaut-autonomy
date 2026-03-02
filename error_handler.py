import logging
from typing import Callable, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)

class ErrorHandler:
    @staticmethod
    def wrap_endpoint(func: Callable) -> Callable:
        """Decorator to wrap API endpoints with error handling"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"API error: {str(e)}", exc_info=True)
                return {
                    "statusCode": 500,
                    "body": {"error": "Internal server error"},
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    }
                }
        return wrapper
        
    @staticmethod
    def wrap_background_task(func: Callable) -> Callable:
        """Decorator to wrap background tasks with error handling"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Background task error: {str(e)}", exc_info=True)
                return {"success": False, "error": str(e)}
        return wrapper

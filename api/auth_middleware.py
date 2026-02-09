from typing import Dict, Any, Callable, Awaitable
from functools import wraps
from fastapi import HTTPException, status

def authenticate_user(func: Callable[..., Awaitable[Dict[str, Any]]]):
    """Authentication middleware decorator."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # TODO: Implement actual authentication logic
        # For MVP, we'll just check for a basic API key
        api_key = kwargs.get("headers", {}).get("x-api-key")
        if not api_key or api_key != "mvp-key":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        return await func(*args, **kwargs)
    return wrapper

__all__ = ["authenticate_user"]

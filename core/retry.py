"""
Exponential backoff and retry utilities for API calls.

Provides decorators and utility functions for implementing robust
retry logic with exponential backoff and jitter for API calls.
"""

import asyncio
import random
import time
import logging
import functools
from typing import Any, Callable, Optional, Type, Union, List, TypeVar

logger = logging.getLogger(__name__)

# Type for the decorated function
F = TypeVar('F', bound=Callable[..., Any])

# Default retry exceptions
DEFAULT_RETRY_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
)

class RateLimitError(Exception):
    """Exception raised when an API rate limit is hit."""
    pass

class APIConnectionError(Exception):
    """Exception raised when an API connection fails."""
    pass

def exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Optional[Union[Type[Exception], List[Type[Exception]]]] = None
) -> Callable[[F], F]:
    """
    Decorator for exponential backoff with jitter.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add randomness to delay
        retry_exceptions: Exception types to retry on
        
    Returns:
        Decorated function with retry logic
    """
    if retry_exceptions is None:
        retry_exceptions = DEFAULT_RETRY_EXCEPTIONS + (RateLimitError, APIConnectionError)
    
    if not isinstance(retry_exceptions, (list, tuple)):
        retry_exceptions = (retry_exceptions,)
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries - 1:
                        # Last attempt failed, re-raise the exception
                        logger.error(
                            f"All {max_retries} retry attempts failed for {func.__name__}: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter if enabled (between 50% and 100% of delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    # Wait before next attempt
                    await asyncio.sleep(delay)
            
            # This should never happen, but just in case
            raise last_exception or RuntimeError("Unexpected error in retry logic")
        
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries - 1:
                        # Last attempt failed, re-raise the exception
                        logger.error(
                            f"All {max_retries} retry attempts failed for {func.__name__}: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter if enabled (between 50% and 100% of delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    # Wait before next attempt
                    time.sleep(delay)
            
            # This should never happen, but just in case
            raise last_exception or RuntimeError("Unexpected error in retry logic")
        
        # Return appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


# Helper function to calculate backoff delay
def calculate_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> float:
    """
    Calculate backoff delay for a given attempt.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add randomness to delay
        
    Returns:
        float: Delay in seconds
    """
    delay = min(base_delay * (exponential_base ** attempt), max_delay)
    
    if jitter:
        delay = delay * (0.5 + random.random())
    
    return delay

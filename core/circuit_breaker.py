"""
Circuit breaker pattern implementation for external API calls.

This module provides a circuit breaker implementation to prevent cascading failures
when external services are down or experiencing issues. The circuit breaker has three states:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests are rejected immediately
- HALF_OPEN: Testing if service has recovered, limited requests allowed

Usage:
    # Create circuit breakers for each external service
    openrouter_cb = CircuitBreaker('openrouter', failure_threshold=3, recovery_timeout=60)
    
    # Use with async functions
    try:
        result = await openrouter_cb.call(api_client.make_request, *args, **kwargs)
    except CircuitOpenError:
        # Handle circuit open case (use fallback or inform user)
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, cast

logger = logging.getLogger(__name__)

# Type for the function to be called
F = TypeVar('F', bound=Callable[..., Any])

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing - reject calls
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitOpenError(Exception):
    """Exception raised when a circuit is open."""
    pass

class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against cascading failures.
    
    Attributes:
        name: Identifier for this circuit breaker
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        half_open_max_calls: Maximum calls allowed in half-open state
        state: Current circuit state
        failure_count: Current consecutive failure count
        last_failure_time: Timestamp of last failure
        half_open_calls: Current number of calls in half-open state
        success_count: Consecutive successes in half-open state
        success_threshold: Successes needed in half-open to close circuit
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        success_threshold: int = 2
    ):
        """
        Initialize a new circuit breaker.
        
        Args:
            name: Identifier for this circuit breaker
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Maximum calls allowed in half-open state
            success_threshold: Consecutive successes needed in half-open to close
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        self.success_count = 0
        
        logger.info(f"Circuit breaker '{name}' initialized in CLOSED state")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call a function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of the function call
            
        Raises:
            CircuitOpenError: If circuit is OPEN or HALF_OPEN with max calls reached
            Any exception raised by the called function
        """
        self._check_state_transition()
        
        if self.state == CircuitState.OPEN:
            logger.warning(f"Circuit '{self.name}' is OPEN - rejecting call")
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                logger.warning(f"Circuit '{self.name}' is HALF_OPEN with max calls reached")
                raise CircuitOpenError(f"Circuit '{self.name}' is HALF_OPEN, max calls reached")
            self.half_open_calls += 1
            logger.info(f"Circuit '{self.name}' is HALF_OPEN - allowing test call {self.half_open_calls}")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure()
            logger.warning(f"Circuit '{self.name}' recorded failure: {type(e).__name__}: {e}")
            raise
    
    def _check_state_transition(self) -> None:
        """Check if circuit state should transition based on time elapsed."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                self.success_count = 0
                logger.info(f"Circuit '{self.name}' transitioned from OPEN to HALF_OPEN")
    
    def _on_success(self) -> None:
        """Handle a successful call."""
        if self.state == CircuitState.CLOSED:
            # Reset failure count on success in closed state
            self.failure_count = 0
        elif self.state == CircuitState.HALF_OPEN:
            # In half-open, track consecutive successes
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                # Transition to closed after enough successes
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit '{self.name}' transitioned from HALF_OPEN to CLOSED")
    
    def _on_failure(self) -> None:
        """Handle a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            # Transition to open after threshold failures
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit '{self.name}' transitioned from CLOSED to OPEN after {self.failure_count} failures")
        elif self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open returns to open
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit '{self.name}' transitioned from HALF_OPEN back to OPEN after failure")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        elapsed = datetime.now() - self.last_failure_time
        return elapsed > timedelta(seconds=self.recovery_timeout)
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        self.success_count = 0
        logger.info(f"Circuit '{self.name}' manually reset to CLOSED state")
    
    def force_open(self) -> None:
        """Manually force the circuit breaker to open state."""
        self.state = CircuitState.OPEN
        self.last_failure_time = datetime.now()
        logger.warning(f"Circuit '{self.name}' manually forced to OPEN state")
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN


# Global registry of circuit breakers
_circuit_breakers: Dict[str, CircuitBreaker] = {}

def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get a circuit breaker by name."""
    return _circuit_breakers.get(name)

def register_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    recovery_timeout: float = 60.0,
    half_open_max_calls: int = 1,
    success_threshold: int = 2
) -> CircuitBreaker:
    """
    Register a new circuit breaker or get existing one.
    
    Args:
        name: Identifier for this circuit breaker
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        half_open_max_calls: Maximum calls allowed in half-open state
        success_threshold: Consecutive successes needed in half-open to close
        
    Returns:
        CircuitBreaker: New or existing circuit breaker
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            success_threshold=success_threshold
        )
    return _circuit_breakers[name]

# Initialize common circuit breakers
def initialize_common_circuit_breakers():
    """Initialize circuit breakers for common external services."""
    register_circuit_breaker('openrouter', failure_threshold=3, recovery_timeout=60)
    register_circuit_breaker('github', failure_threshold=5, recovery_timeout=120)
    register_circuit_breaker('neon_db', failure_threshold=3, recovery_timeout=30)
    register_circuit_breaker('railway', failure_threshold=3, recovery_timeout=60)
    register_circuit_breaker('slack', failure_threshold=3, recovery_timeout=30)
    register_circuit_breaker('puppeteer', failure_threshold=3, recovery_timeout=45)

# Initialize on import
initialize_common_circuit_breakers()

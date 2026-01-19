"""
Retry handler with exponential backoff and circuit breaker pattern.

Provides reliable API call wrapping for GitHub, Railway, and database operations.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic return types
T = TypeVar("T")

# Configurable constants
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_BASE_DELAY_SECONDS: float = 1.0
DEFAULT_MAX_DELAY_SECONDS: float = 60.0
DEFAULT_EXPONENTIAL_BASE: float = 2.0
CIRCUIT_FAILURE_THRESHOLD: int = 5
CIRCUIT_RESET_TIMEOUT_SECONDS: int = 30


class CircuitState(Enum):
    """States for the circuit breaker pattern."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failure threshold exceeded, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = DEFAULT_MAX_RETRIES
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE
    retryable_exceptions: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (ConnectionError, TimeoutError, OSError)
    )


@dataclass
class CircuitBreakerState:
    """Tracks circuit breaker state for a specific service."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    success_count_in_half_open: int = 0


class CircuitBreaker:
    """
    Implements the circuit breaker pattern for fault tolerance.

    Prevents cascading failures by stopping requests to failing services.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
        reset_timeout_seconds: int = CIRCUIT_RESET_TIMEOUT_SECONDS,
    ):
        """
        Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit.
            reset_timeout_seconds: Seconds before attempting recovery.
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = timedelta(seconds=reset_timeout_seconds)
        self._states: dict[str, CircuitBreakerState] = defaultdict(
            CircuitBreakerState
        )

    def can_execute(self, service_name: str) -> bool:
        """
        Check if a request can be made to the service.

        Args:
            service_name: Identifier for the service (e.g., 'github', 'railway').

        Returns:
            True if the request should proceed, False otherwise.
        """
        cb_state = self._states[service_name]

        if cb_state.state == CircuitState.CLOSED:
            return True

        if cb_state.state == CircuitState.OPEN:
            if cb_state.last_failure_time:
                time_since_failure = datetime.utcnow() - cb_state.last_failure_time
                if time_since_failure >= self.reset_timeout:
                    logger.info(
                        "Circuit breaker for %s transitioning to HALF_OPEN",
                        service_name,
                    )
                    cb_state.state = CircuitState.HALF_OPEN
                    cb_state.success_count_in_half_open = 0
                    return True
            return False

        return True

    def record_success(self, service_name: str) -> None:
        """
        Record a successful request.

        Args:
            service_name: Identifier for the service.
        """
        cb_state = self._states[service_name]

        if cb_state.state == CircuitState.HALF_OPEN:
            cb_state.success_count_in_half_open += 1
            if cb_state.success_count_in_half_open >= 2:
                logger.info(
                    "Circuit breaker for %s reset to CLOSED", service_name
                )
                cb_state.state = CircuitState.CLOSED
                cb_state.failure_count = 0

        elif cb_state.state == CircuitState.CLOSED:
            cb_state.failure_count = 0

    def record_failure(self, service_name: str) -> None:
        """
        Record a failed request.

        Args:
            service_name: Identifier for the service.
        """
        cb_state = self._states[service_name]
        cb_state.failure_count += 1
        cb_state.last_failure_time = datetime.utcnow()

        if cb_state.state == CircuitState.HALF_OPEN:
            logger.warning(
                "Circuit breaker for %s reopened after failure in HALF_OPEN",
                service_name,
            )
            cb_state.state = CircuitState.OPEN

        elif (
            cb_state.state == CircuitState.CLOSED
            and cb_state.failure_count >= self.failure_threshold
        ):
            logger.warning(
                "Circuit breaker for %s OPENED after %d failures",
                service_name,
                cb_state.failure_count,
            )
            cb_state.state = CircuitState.OPEN

    def get_state(self, service_name: str) -> CircuitState:
        """
        Get the current state of the circuit breaker.

        Args:
            service_name: Identifier for the service.

        Returns:
            Current circuit state.
        """
        return self._states[service_name].state


_circuit_breaker = CircuitBreaker()


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and requests are blocked."""

    def __init__(self, service_name: str):
        """
        Initialize the error.

        Args:
            service_name: The service that is unavailable.
        """
        super().__init__(f"Circuit breaker open for service: {service_name}")
        self.service_name = service_name


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: The current attempt number (0-based).
        base_delay: Base delay in seconds.
        max_delay: Maximum delay in seconds.
        exponential_base: Base for exponential calculation.

    Returns:
        Delay in seconds to wait before next attempt.
    """
    delay = base_delay * (exponential_base**attempt)
    return min(delay, max_delay)


def with_retry(
    service_name: str,
    config: Optional[RetryConfig] = None,
    log_to_db: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that adds retry logic with exponential backoff.

    Args:
        service_name: Identifier for the service (used for circuit breaker).
        config: Retry configuration. Uses defaults if not provided.
        log_to_db: Whether to log retries to the execution_logs table.

    Returns:
        Decorator function.

    Example:
        @with_retry("github")
        def fetch_github_data():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if not _circuit_breaker.can_execute(service_name):
                logger.warning(
                    "Circuit breaker OPEN for %s, skipping %s",
                    service_name,
                    func.__name__,
                )
                raise CircuitOpenError(service_name)

            last_exception: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    _circuit_breaker.record_success(service_name)
                    return result

                except config.retryable_exceptions as exc:
                    last_exception = exc
                    _circuit_breaker.record_failure(service_name)

                    if attempt < config.max_retries:
                        delay = calculate_backoff_delay(
                            attempt=attempt,
                            base_delay=config.base_delay_seconds,
                            max_delay=config.max_delay_seconds,
                            exponential_base=config.exponential_base,
                        )

                        logger.warning(
                            "%s failed (attempt %d/%d): %s. Retrying in %.1fs",
                            func.__name__,
                            attempt + 1,
                            config.max_retries + 1,
                            str(exc),
                            delay,
                        )

                        if log_to_db:
                            _log_retry_to_db(
                                function_name=func.__name__,
                                service_name=service_name,
                                attempt=attempt + 1,
                                max_attempts=config.max_retries + 1,
                                error_message=str(exc),
                                delay_seconds=delay,
                            )

                        time.sleep(delay)
                    else:
                        logger.error(
                            "%s failed after %d attempts. Last error: %s",
                            func.__name__,
                            config.max_retries + 1,
                            str(exc),
                        )

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator


def _log_retry_to_db(
    function_name: str,
    service_name: str,
    attempt: int,
    max_attempts: int,
    error_message: str,
    delay_seconds: float,
) -> None:
    """
    Log a retry event to the execution_logs table.

    Args:
        function_name: Name of the function being retried.
        service_name: Name of the service.
        attempt: Current attempt number.
        max_attempts: Maximum number of attempts.
        error_message: The error that caused the retry.
        delay_seconds: How long until the next retry.
    """
    try:
        from core.database import execute_query

        execute_query(
            """
            INSERT INTO execution_logs (log_type, message, metadata)
            VALUES ($1, $2, $3::jsonb)
            """,
            (
                "retry",
                f"Retrying {function_name} ({service_name}) "
                f"attempt {attempt}/{max_attempts}",
                {
                    "function": function_name,
                    "service": service_name,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "error": error_message,
                    "delay_seconds": delay_seconds,
                },
            ),
        )
    except (ConnectionError, OSError, ImportError) as db_error:
        logger.debug("Failed to log retry to database: %s", db_error)


GITHUB_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay_seconds=2.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)

RAILWAY_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    base_delay_seconds=1.0,
    max_delay_seconds=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay_seconds=0.5,
    max_delay_seconds=10.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)


def get_circuit_breaker() -> CircuitBreaker:
    """
    Get the global circuit breaker instance.

    Returns:
        The global CircuitBreaker instance.
    """
    return _circuit_breaker

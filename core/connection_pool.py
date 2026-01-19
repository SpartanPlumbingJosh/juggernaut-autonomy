"""
JUGGERNAUT Connection Pool and Retry Logic

Provides connection pooling for HTTP-based PostgreSQL connections
and exponential backoff retry for transient failures.
"""

import json
import logging
import random
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, TypeVar
from queue import Queue, Empty
from contextlib import contextmanager

# Configure module logger
logger = logging.getLogger(__name__)

# ==========================================================================
# CONFIGURATION CONSTANTS
# ==========================================================================

# Connection pool settings
DEFAULT_POOL_SIZE: int = 10
MAX_POOL_SIZE: int = 50
MIN_POOL_SIZE: int = 1
CONNECTION_TIMEOUT_SECONDS: int = 30
POOL_ACQUIRE_TIMEOUT_SECONDS: float = 5.0

# Retry settings
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_BASE_DELAY_SECONDS: float = 0.5
DEFAULT_MAX_DELAY_SECONDS: float = 30.0
DEFAULT_EXPONENTIAL_BASE: float = 2.0
DEFAULT_JITTER_FACTOR: float = 0.1

# Transient error codes that should trigger retry
TRANSIENT_HTTP_CODES: List[int] = [
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
]

# ==========================================================================
# DATA CLASSES
# ==========================================================================


@dataclass
class RetryConfig:
    """Configuration for retry behavior.
    
    Attributes:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        exponential_base: Base for exponential backoff calculation.
        jitter_factor: Random jitter factor (0-1) to prevent thundering herd.
    """
    max_retries: int = DEFAULT_MAX_RETRIES
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE
    jitter_factor: float = DEFAULT_JITTER_FACTOR


@dataclass
class PoolConfig:
    """Configuration for connection pool.
    
    Attributes:
        pool_size: Number of connections to maintain in pool.
        connection_timeout: Timeout for individual connections in seconds.
        acquire_timeout: Timeout for acquiring a connection from pool in seconds.
    """
    pool_size: int = DEFAULT_POOL_SIZE
    connection_timeout: int = CONNECTION_TIMEOUT_SECONDS
    acquire_timeout: float = POOL_ACQUIRE_TIMEOUT_SECONDS


@dataclass
class PooledConnection:
    """A pooled HTTP connection wrapper.
    
    Attributes:
        endpoint: The HTTP endpoint URL.
        connection_string: Database connection string.
        created_at: Timestamp when connection was created.
        last_used: Timestamp when connection was last used.
        use_count: Number of times this connection has been used.
    """
    endpoint: str
    connection_string: str
    created_at: float
    last_used: float
    use_count: int = 0


# ==========================================================================
# RETRY LOGIC
# ==========================================================================

T = TypeVar('T')


def calculate_backoff_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    Calculate delay for exponential backoff with jitter.
    
    Args:
        attempt: Current attempt number (0-indexed).
        config: Retry configuration.
    
    Returns:
        Delay in seconds before next retry attempt.
    """
    # Calculate exponential delay
    exponential_delay = config.base_delay * (config.exponential_base ** attempt)
    
    # Cap at max delay
    capped_delay = min(exponential_delay, config.max_delay)
    
    # Add jitter to prevent thundering herd
    jitter = capped_delay * config.jitter_factor * random.random()
    
    return capped_delay + jitter


def is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient and should trigger retry.
    
    Args:
        error: The exception to check.
    
    Returns:
        True if the error is transient and retryable.
    """
    if isinstance(error, urllib.error.HTTPError):
        return error.code in TRANSIENT_HTTP_CODES
    
    if isinstance(error, urllib.error.URLError):
        # Network errors are typically transient
        error_str = str(error.reason).lower()
        transient_indicators = [
            'timeout',
            'connection refused',
            'connection reset',
            'temporary failure',
            'name resolution',
        ]
        return any(indicator in error_str for indicator in transient_indicators)
    
    if isinstance(error, TimeoutError):
        return True
    
    if isinstance(error, ConnectionError):
        return True
    
    return False


def with_retry(
    config: Optional[RetryConfig] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that adds exponential backoff retry to a function.
    
    Args:
        config: Retry configuration. Uses defaults if not provided.
    
    Returns:
        Decorated function with retry logic.
    
    Example:
        @with_retry(RetryConfig(max_retries=5))
        def fetch_data():
            return make_http_request()
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Optional[Exception] = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as error:
                    last_error = error
                    
                    if not is_transient_error(error):
                        logger.warning(
                            "Non-transient error in %s: %s",
                            func.__name__,
                            error
                        )
                        raise
                    
                    if attempt >= config.max_retries:
                        logger.error(
                            "Max retries (%d) exceeded for %s: %s",
                            config.max_retries,
                            func.__name__,
                            error
                        )
                        raise
                    
                    delay = calculate_backoff_delay(attempt, config)
                    logger.info(
                        "Retry %d/%d for %s after %.2fs: %s",
                        attempt + 1,
                        config.max_retries,
                        func.__name__,
                        delay,
                        error
                    )
                    time.sleep(delay)
            
            # This should never be reached, but satisfies type checker
            if last_error:
                raise last_error
            raise RuntimeError(f"Unexpected state in retry logic for {func.__name__}")
        
        return wrapper
    return decorator


# ==========================================================================
# CONNECTION POOL
# ==========================================================================


class ConnectionPool:
    """
    Thread-safe connection pool for HTTP-based database connections.
    
    Manages a pool of reusable connection configurations to reduce
    overhead when making multiple database queries concurrently.
    
    Attributes:
        endpoint: The database HTTP endpoint.
        connection_string: Database connection string.
        config: Pool configuration.
    """
    
    def __init__(
        self,
        endpoint: str,
        connection_string: str,
        config: Optional[PoolConfig] = None
    ) -> None:
        """
        Initialize the connection pool.
        
        Args:
            endpoint: The database HTTP endpoint URL.
            connection_string: Database connection string for authentication.
            config: Pool configuration. Uses defaults if not provided.
        """
        self.endpoint = endpoint
        self.connection_string = connection_string
        self.config = config or PoolConfig()
        
        # Validate pool size
        if not MIN_POOL_SIZE <= self.config.pool_size <= MAX_POOL_SIZE:
            raise ValueError(
                f"Pool size must be between {MIN_POOL_SIZE} and {MAX_POOL_SIZE}, "
                f"got {self.config.pool_size}"
            )
        
        self._pool: Queue[PooledConnection] = Queue(maxsize=self.config.pool_size)
        self._lock = Lock()
        self._total_connections = 0
        self._stats = {
            'connections_created': 0,
            'connections_reused': 0,
            'acquire_timeouts': 0,
            'queries_executed': 0,
            'queries_failed': 0,
        }
        
        logger.info(
            "Initialized connection pool: endpoint=%s, size=%d",
            self.endpoint,
            self.config.pool_size
        )
    
    def _create_connection(self) -> PooledConnection:
        """
        Create a new pooled connection.
        
        Returns:
            A new PooledConnection instance.
        """
        now = time.time()
        connection = PooledConnection(
            endpoint=self.endpoint,
            connection_string=self.connection_string,
            created_at=now,
            last_used=now,
            use_count=0
        )
        
        with self._lock:
            self._total_connections += 1
            self._stats['connections_created'] += 1
        
        logger.debug(
            "Created new connection, total=%d",
            self._total_connections
        )
        
        return connection
    
    @contextmanager
    def acquire(self):
        """
        Acquire a connection from the pool.
        
        Returns a context manager that yields a PooledConnection
        and automatically returns it to the pool when done.
        
        Yields:
            A PooledConnection instance.
        
        Raises:
            TimeoutError: If unable to acquire connection within timeout.
        
        Example:
            with pool.acquire() as conn:
                result = execute_query(conn, sql)
        """
        connection: Optional[PooledConnection] = None
        
        try:
            # Try to get existing connection from pool
            connection = self._pool.get(
                block=True,
                timeout=self.config.acquire_timeout
            )
            connection.use_count += 1
            connection.last_used = time.time()
            
            with self._lock:
                self._stats['connections_reused'] += 1
            
            logger.debug(
                "Reused connection, use_count=%d",
                connection.use_count
            )
            
        except Empty:
            # Pool empty, check if we can create new connection
            with self._lock:
                if self._total_connections < self.config.pool_size:
                    connection = self._create_connection()
                else:
                    self._stats['acquire_timeouts'] += 1
                    raise TimeoutError(
                        f"Unable to acquire connection within "
                        f"{self.config.acquire_timeout}s, pool exhausted"
                    )
        
        try:
            yield connection
        finally:
            # Return connection to pool
            if connection:
                try:
                    self._pool.put_nowait(connection)
                except Exception:
                    # Pool full, connection will be garbage collected
                    with self._lock:
                        self._total_connections -= 1
                    logger.debug("Connection not returned to pool (full)")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current pool statistics.
        
        Returns:
            Dictionary containing pool statistics.
        """
        with self._lock:
            return {
                **self._stats,
                'pool_size': self.config.pool_size,
                'total_connections': self._total_connections,
                'available_connections': self._pool.qsize(),
            }
    
    def close(self) -> None:
        """
        Close the connection pool and release all connections.
        """
        logger.info("Closing connection pool")
        
        # Drain the pool
        while True:
            try:
                self._pool.get_nowait()
                with self._lock:
                    self._total_connections -= 1
            except Empty:
                break
        
        logger.info("Connection pool closed")


# ==========================================================================
# POOLED DATABASE CLIENT
# ==========================================================================


class PooledDatabaseClient:
    """
    Database client with connection pooling and retry logic.
    
    Wraps the standard database operations with connection pooling
    for better concurrent performance and automatic retry for
    transient failures.
    """
    
    def __init__(
        self,
        endpoint: str,
        connection_string: str,
        pool_config: Optional[PoolConfig] = None,
        retry_config: Optional[RetryConfig] = None
    ) -> None:
        """
        Initialize the pooled database client.
        
        Args:
            endpoint: Database HTTP endpoint URL.
            connection_string: Database connection string.
            pool_config: Connection pool configuration.
            retry_config: Retry configuration.
        """
        self.pool = ConnectionPool(endpoint, connection_string, pool_config)
        self.retry_config = retry_config or RetryConfig()
        
        logger.info("Initialized pooled database client")
    
    @with_retry()
    def query(self, sql: str) -> Dict[str, Any]:
        """
        Execute a SQL query with pooled connection and retry logic.
        
        Args:
            sql: SQL query string to execute.
        
        Returns:
            Query result dictionary with 'rows', 'rowCount', etc.
        
        Raises:
            Exception: If query fails after all retries.
        """
        with self.pool.acquire() as connection:
            headers = {
                "Content-Type": "application/json",
                "Neon-Connection-String": connection.connection_string
            }
            
            data = json.dumps({"query": sql}).encode('utf-8')
            request = urllib.request.Request(
                connection.endpoint,
                data=data,
                headers=headers,
                method='POST'
            )
            
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.pool.config.connection_timeout
                ) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    
                    # Check for database-level errors
                    if "message" in result:
                        severity = str(result.get("severity", "")).lower()
                        if "error" in severity:
                            raise Exception(f"Database error: {result['message']}")
                    
                    with self.pool._lock:
                        self.pool._stats['queries_executed'] += 1
                    
                    return result
                    
            except Exception as error:
                with self.pool._lock:
                    self.pool._stats['queries_failed'] += 1
                raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get combined pool and query statistics.
        
        Returns:
            Dictionary containing all statistics.
        """
        return self.pool.get_stats()
    
    def close(self) -> None:
        """
        Close the database client and release resources.
        """
        self.pool.close()


# ==========================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# ==========================================================================

_pooled_client: Optional[PooledDatabaseClient] = None
_client_lock = Lock()


def get_pooled_client(
    endpoint: str,
    connection_string: str,
    pool_config: Optional[PoolConfig] = None,
    retry_config: Optional[RetryConfig] = None
) -> PooledDatabaseClient:
    """
    Get or create a singleton pooled database client.
    
    Thread-safe factory function that returns a shared
    PooledDatabaseClient instance.
    
    Args:
        endpoint: Database HTTP endpoint URL.
        connection_string: Database connection string.
        pool_config: Connection pool configuration.
        retry_config: Retry configuration.
    
    Returns:
        Shared PooledDatabaseClient instance.
    """
    global _pooled_client
    
    with _client_lock:
        if _pooled_client is None:
            _pooled_client = PooledDatabaseClient(
                endpoint=endpoint,
                connection_string=connection_string,
                pool_config=pool_config,
                retry_config=retry_config
            )
        return _pooled_client


def query_with_pool(
    sql: str,
    endpoint: str,
    connection_string: str
) -> Dict[str, Any]:
    """
    Execute a query using the pooled client.
    
    Convenience function that uses the singleton pooled client.
    
    Args:
        sql: SQL query to execute.
        endpoint: Database HTTP endpoint URL.
        connection_string: Database connection string.
    
    Returns:
        Query result dictionary.
    """
    client = get_pooled_client(endpoint, connection_string)
    return client.query(sql)


def get_pool_stats() -> Optional[Dict[str, Any]]:
    """
    Get current pool statistics if client exists.
    
    Returns:
        Pool statistics dictionary or None if no client initialized.
    """
    if _pooled_client:
        return _pooled_client.get_stats()
    return None

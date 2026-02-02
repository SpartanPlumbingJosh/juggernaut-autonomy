"""
Database connection pooling for JUGGERNAUT.

This module provides a connection pool for PostgreSQL using asyncpg,
implementing the PgBouncer pattern for efficient connection management.
It handles connection lifecycle, retries, and graceful error handling.

Usage:
    from core.connection import DatabasePool
    
    # Get a connection from the pool
    async with DatabasePool() as pool:
        async with pool.acquire() as conn:
            # Use the connection
            result = await conn.fetch("SELECT * FROM users")
"""

import asyncio
import json
import logging
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

import asyncpg

logger = logging.getLogger(__name__)

# Default connection parameters
DEFAULT_MIN_CONNECTIONS = 5
DEFAULT_MAX_CONNECTIONS = 20
DEFAULT_MAX_INACTIVE_CONNECTION_LIFETIME = 300.0  # 5 minutes
DEFAULT_CONNECTION_TIMEOUT = 30.0  # 30 seconds
DEFAULT_COMMAND_TIMEOUT = 60.0  # 60 seconds

class DatabaseError(Exception):
    """Exception raised for database errors."""
    pass

class DatabasePool:
    """Connection pool for PostgreSQL using asyncpg."""
    
    _instance = None
    _pool = None
    _initialized = False
    _connection_params = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one pool is created."""
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        min_connections: int = DEFAULT_MIN_CONNECTIONS,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        max_inactive_connection_lifetime: float = DEFAULT_MAX_INACTIVE_CONNECTION_LIFETIME,
        connection_timeout: float = DEFAULT_CONNECTION_TIMEOUT,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT
    ):
        """
        Initialize the database pool.
        
        Args:
            connection_string: PostgreSQL connection string
            min_connections: Minimum number of connections in the pool
            max_connections: Maximum number of connections in the pool
            max_inactive_connection_lifetime: Maximum time in seconds a connection can be inactive
            connection_timeout: Timeout for establishing connections
            command_timeout: Timeout for executing commands
        """
        if self._initialized:
            return
        
        # Get connection string from environment if not provided
        if connection_string is None:
            connection_string = self._get_connection_string_from_env()
        
        # Store connection parameters
        self._connection_params = {
            "dsn": connection_string,
            "min_size": min_connections,
            "max_size": max_connections,
            "max_inactive_connection_lifetime": max_inactive_connection_lifetime,
            "timeout": connection_timeout,
            "command_timeout": command_timeout
        }
        
        self._initialized = True
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Don't close the pool here, as it's a singleton
        # The pool will be closed when the application exits
        pass
    
    async def initialize(self) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            return
        
        try:
            self._pool = await asyncpg.create_pool(**self._connection_params)
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise DatabaseError(f"Failed to initialize database pool: {e}")
    
    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed")
    
    def acquire(self):
        """
        Acquire a connection from the pool.
        
        Returns:
            Connection context manager
        
        Raises:
            DatabaseError: If the pool is not initialized
        """
        if self._pool is None:
            raise DatabaseError("Database pool not initialized")
        
        return self._pool.acquire()
    
    async def execute(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            timeout: Query timeout in seconds
            
        Returns:
            Dict with query results
            
        Raises:
            DatabaseError: If the query fails
        """
        if self._pool is None:
            await self.initialize()
        
        start_time = time.time()
        params = params or []
        
        try:
            async with self._pool.acquire() as conn:
                if timeout:
                    result = await asyncio.wait_for(conn.execute(query, *params), timeout)
                else:
                    result = await conn.execute(query, *params)
                
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(f"Query executed in {duration_ms:.2f}ms")
                
                return {"success": True, "result": result, "duration_ms": duration_ms}
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Query timed out after {duration_ms:.2f}ms")
            raise DatabaseError(f"Query timed out after {duration_ms:.2f}ms")
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Query failed after {duration_ms:.2f}ms: {e}")
            raise DatabaseError(f"Query failed: {e}")
    
    async def fetch(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Fetch rows from a SQL query.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            timeout: Query timeout in seconds
            
        Returns:
            Dict with query results
            
        Raises:
            DatabaseError: If the query fails
        """
        if self._pool is None:
            await self.initialize()
        
        start_time = time.time()
        params = params or []
        
        try:
            async with self._pool.acquire() as conn:
                if timeout:
                    rows = await asyncio.wait_for(conn.fetch(query, *params), timeout)
                else:
                    rows = await conn.fetch(query, *params)
                
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(f"Query fetched {len(rows)} rows in {duration_ms:.2f}ms")
                
                # Convert rows to dicts
                result_rows = [dict(row) for row in rows]
                
                return {
                    "success": True,
                    "rows": result_rows,
                    "rowCount": len(result_rows),
                    "duration_ms": duration_ms
                }
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Query timed out after {duration_ms:.2f}ms")
            raise DatabaseError(f"Query timed out after {duration_ms:.2f}ms")
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Query failed after {duration_ms:.2f}ms: {e}")
            raise DatabaseError(f"Query failed: {e}")
    
    async def fetchrow(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Fetch a single row from a SQL query.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            timeout: Query timeout in seconds
            
        Returns:
            Dict with query results
            
        Raises:
            DatabaseError: If the query fails
        """
        if self._pool is None:
            await self.initialize()
        
        start_time = time.time()
        params = params or []
        
        try:
            async with self._pool.acquire() as conn:
                if timeout:
                    row = await asyncio.wait_for(conn.fetchrow(query, *params), timeout)
                else:
                    row = await conn.fetchrow(query, *params)
                
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(f"Query fetched row in {duration_ms:.2f}ms")
                
                # Convert row to dict
                result_row = dict(row) if row else None
                
                return {
                    "success": True,
                    "row": result_row,
                    "found": result_row is not None,
                    "duration_ms": duration_ms
                }
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Query timed out after {duration_ms:.2f}ms")
            raise DatabaseError(f"Query timed out after {duration_ms:.2f}ms")
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Query failed after {duration_ms:.2f}ms: {e}")
            raise DatabaseError(f"Query failed: {e}")
    
    async def transaction(self):
        """
        Start a transaction.
        
        Returns:
            Transaction context manager
        
        Raises:
            DatabaseError: If the pool is not initialized
        """
        if self._pool is None:
            await self.initialize()
        
        conn = await self._pool.acquire()
        
        class TransactionContextManager:
            def __init__(self, conn):
                self.conn = conn
                self.transaction = None
            
            async def __aenter__(self):
                self.transaction = self.conn.transaction()
                await self.transaction.__aenter__()
                return self.conn
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                await self.transaction.__aexit__(exc_type, exc_val, exc_tb)
                await self.conn.close()
        
        return TransactionContextManager(conn)
    
    def _get_connection_string_from_env(self) -> str:
        """
        Get database connection string from environment variables.
        
        Returns:
            Connection string
            
        Raises:
            DatabaseError: If no connection string is found
        """
        # Try DATABASE_URL first (Railway standard)
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            return database_url
        
        # Try NEON_CONNECTION_STRING
        neon_connection_string = os.environ.get("NEON_CONNECTION_STRING")
        if neon_connection_string:
            return neon_connection_string
        
        # Try to build from individual components
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5432")
        user = os.environ.get("DB_USER", "postgres")
        password = os.environ.get("DB_PASSWORD", "")
        database = os.environ.get("DB_NAME", "postgres")
        
        # Build connection string
        connection_string = f"postgresql://{user}:{urllib.parse.quote_plus(password)}@{host}:{port}/{database}"
        
        return connection_string

# Global pool instance
_pool = None

async def get_pool() -> DatabasePool:
    """
    Get the global database pool instance.
    
    Returns:
        DatabasePool instance
    """
    global _pool
    if _pool is None:
        _pool = DatabasePool()
        await _pool.initialize()
    return _pool

async def execute_query(
    query: str,
    params: Optional[List[Any]] = None,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Execute a SQL query using the global pool.
    
    Args:
        query: SQL query to execute
        params: Query parameters
        timeout: Query timeout in seconds
        
    Returns:
        Dict with query results
        
    Raises:
        DatabaseError: If the query fails
    """
    pool = await get_pool()
    return await pool.execute(query, params, timeout)

async def fetch_rows(
    query: str,
    params: Optional[List[Any]] = None,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Fetch rows from a SQL query using the global pool.
    
    Args:
        query: SQL query to execute
        params: Query parameters
        timeout: Query timeout in seconds
        
    Returns:
        Dict with query results
        
    Raises:
        DatabaseError: If the query fails
    """
    pool = await get_pool()
    return await pool.fetch(query, params, timeout)

async def fetch_row(
    query: str,
    params: Optional[List[Any]] = None,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Fetch a single row from a SQL query using the global pool.
    
    Args:
        query: SQL query to execute
        params: Query parameters
        timeout: Query timeout in seconds
        
    Returns:
        Dict with query results
        
    Raises:
        DatabaseError: If the query fails
    """
    pool = await get_pool()
    return await pool.fetchrow(query, params, timeout)

async def with_transaction(func, *args, **kwargs):
    """
    Execute a function within a transaction.
    
    Args:
        func: Function to execute
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        Exception: If the function raises an exception
    """
    pool = await get_pool()
    
    async with pool.transaction() as conn:
        return await func(conn, *args, **kwargs)

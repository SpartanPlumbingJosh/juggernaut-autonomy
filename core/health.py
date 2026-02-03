"""
Health check system for JUGGERNAUT services.

This module provides health check endpoints and utilities for monitoring
the health of JUGGERNAUT services. It includes database connection checks,
external API dependency checks, and worker status checks.

Usage:
    from core.health import HealthCheck, register_health_check
    
    # Create a health check for a service
    health_check = HealthCheck("main-service")
    
    # Register component checks
    @register_health_check(health_check)
    async def check_database():
        # Check database connection
        try:
            result = await query_db("SELECT 1")
            return True, "Database connection OK"
        except Exception as e:
            return False, f"Database connection failed: {e}"
    
    # Use in FastAPI app
    @app.get("/health")
    async def health():
        return await health_check.check()
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .database import query_db

logger = logging.getLogger(__name__)

class HealthCheckError(Exception):
    """Exception raised for errors in health checks."""
    pass

class HealthCheck:
    """Health check manager for a service."""
    
    def __init__(self, service_name: str):
        """
        Initialize a health check manager.
        
        Args:
            service_name: Name of the service
        """
        self.service_name = service_name
        self.checks = {}
        self.last_check_time = None
        self.last_check_result = None
        self.startup_time = datetime.now()
    
    async def check(self) -> Dict[str, Any]:
        """
        Run all registered health checks.
        
        Returns:
            Health check result with overall status and component details
        """
        start_time = time.time()
        self.last_check_time = datetime.now()
        
        results = {}
        overall_status = "healthy"
        
        # Run all checks concurrently
        check_tasks = []
        for name, check_func in self.checks.items():
            check_tasks.append(self._run_check(name, check_func))
        
        if check_tasks:
            check_results = await asyncio.gather(*check_tasks, return_exceptions=True)
            
            for name, result in zip(self.checks.keys(), check_results):
                if isinstance(result, Exception):
                    results[name] = {
                        "status": "error",
                        "message": f"Check failed with exception: {result}",
                        "error": str(result)
                    }
                    overall_status = "unhealthy"
                else:
                    status, message, details = result
                    results[name] = {
                        "status": "healthy" if status else "unhealthy",
                        "message": message
                    }
                    
                    if details:
                        results[name]["details"] = details
                    
                    if not status and overall_status != "unhealthy":
                        overall_status = "degraded"
        
        # Add system info
        uptime_seconds = (datetime.now() - self.startup_time).total_seconds()
        
        result = {
            "status": overall_status,
            "service": self.service_name,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": uptime_seconds,
            "checks": results,
            "response_time_ms": int((time.time() - start_time) * 1000)
        }
        
        self.last_check_result = result
        
        return result
    
    async def _run_check(self, name: str, check_func: Callable) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Run a single health check with timeout.
        
        Args:
            name: Name of the check
            check_func: Check function
            
        Returns:
            Tuple of (status, message, details)
        """
        try:
            # Run check with timeout
            result = await asyncio.wait_for(check_func(), timeout=5.0)
            
            if isinstance(result, tuple):
                if len(result) == 2:
                    status, message = result
                    details = None
                elif len(result) == 3:
                    status, message, details = result
                else:
                    status, message = True, str(result)
                    details = None
            else:
                status = bool(result)
                message = "Check passed" if status else "Check failed"
                details = None
            
            return status, message, details
        except asyncio.TimeoutError:
            return False, f"Check timed out after 5 seconds", None
        except Exception as e:
            logger.exception("Health check '%s' failed with exception", name)
            return False, f"Check failed with exception: {e}", {"exception": str(e)}
    
    def register(self, name: str, check_func: Callable) -> None:
        """
        Register a health check function.
        
        Args:
            name: Name of the check
            check_func: Async function that returns (status, message, [details])
        """
        self.checks[name] = check_func
        logger.debug(f"Registered health check '{name}' for service '{self.service_name}'")

def register_health_check(health_check: HealthCheck, name: Optional[str] = None):
    """
    Decorator to register a health check function.
    
    Args:
        health_check: HealthCheck instance
        name: Optional name for the check (defaults to function name)
        
    Returns:
        Decorator function
    """
    def decorator(func):
        check_name = name or func.__name__
        health_check.register(check_name, func)
        return func
    return decorator

# Common health checks

async def check_database_connection() -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Check database connection health.
    
    Returns:
        Tuple of (status, message, details)
    """
    try:
        start_time = time.time()
        result = await query_db("SELECT 1 as db_check")
        
        if not result or "rows" not in result or not result["rows"]:
            return False, "Database query failed", None
        
        response_time = (time.time() - start_time) * 1000
        
        return True, "Database connection healthy", {
            "response_time_ms": int(response_time)
        }
    except Exception as e:
        return False, f"Database connection failed: {e}", None

async def check_redis_connection(redis_client) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Check Redis connection health.
    
    Args:
        redis_client: Redis client instance
        
    Returns:
        Tuple of (status, message, details)
    """
    try:
        start_time = time.time()
        await redis_client.ping()
        
        response_time = (time.time() - start_time) * 1000
        
        return True, "Redis connection healthy", {
            "response_time_ms": int(response_time)
        }
    except Exception as e:
        return False, f"Redis connection failed: {e}", None

async def check_worker_registry() -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Check worker registry health.
    
    Returns:
        Tuple of (status, message, details)
    """
    try:
        result = await query_db(
            """
            SELECT 
                COUNT(*) as total_workers,
                COUNT(*) FILTER (WHERE status = 'active') as active_workers,
                COUNT(*) FILTER (WHERE last_heartbeat > NOW() - INTERVAL '5 minutes') as recent_workers
            FROM worker_registry
            """
        )
        
        if not result or "rows" not in result or not result["rows"]:
            return False, "Worker registry query failed", None
        
        stats = result["rows"][0]
        total = int(stats.get("total_workers", 0))
        active = int(stats.get("active_workers", 0))
        recent = int(stats.get("recent_workers", 0))
        
        if total == 0:
            return False, "No workers registered", stats
        
        if recent == 0:
            return False, "No workers have sent heartbeats recently", stats
        
        if active > 0 and recent / active < 0.5:
            return False, f"Only {recent} of {active} active workers have sent recent heartbeats", stats
        
        return True, f"{recent} of {total} workers active and healthy", stats
    except Exception as e:
        return False, f"Worker registry check failed: {e}", None

async def check_memory_usage() -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Check system memory usage.
    
    Returns:
        Tuple of (status, message, details)
    """
    try:
        import psutil
        
        memory = psutil.virtual_memory()
        percent_used = memory.percent
        
        details = {
            "total_mb": memory.total / (1024 * 1024),
            "available_mb": memory.available / (1024 * 1024),
            "used_mb": memory.used / (1024 * 1024),
            "percent_used": percent_used
        }
        
        if percent_used > 90:
            return False, f"Memory usage critical: {percent_used}%", details
        elif percent_used > 80:
            return False, f"Memory usage high: {percent_used}%", details
        else:
            return True, f"Memory usage normal: {percent_used}%", details
    except ImportError:
        return True, "Memory usage check skipped (psutil not available)", None
    except Exception as e:
        return False, f"Memory usage check failed: {e}", None

async def check_disk_usage() -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Check disk usage.
    
    Returns:
        Tuple of (status, message, details)
    """
    try:
        import psutil
        
        disk = psutil.disk_usage('/')
        percent_used = disk.percent
        
        details = {
            "total_gb": disk.total / (1024 * 1024 * 1024),
            "free_gb": disk.free / (1024 * 1024 * 1024),
            "used_gb": disk.used / (1024 * 1024 * 1024),
            "percent_used": percent_used
        }
        
        if percent_used > 90:
            return False, f"Disk usage critical: {percent_used}%", details
        elif percent_used > 80:
            return False, f"Disk usage high: {percent_used}%", details
        else:
            return True, f"Disk usage normal: {percent_used}%", details
    except ImportError:
        return True, "Disk usage check skipped (psutil not available)", None
    except Exception as e:
        return False, f"Disk usage check failed: {e}", None

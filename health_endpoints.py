"""
Health check endpoints for JUGGERNAUT services.

This module provides HTTP endpoints for health checks that can be used by
Railway's health check system. Each service should import and use the
appropriate health check endpoint.
"""

import json
import logging
from typing import Dict, Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from core.health import HealthCheck, register_health_check
from core.health import check_database_connection, check_worker_registry
from core.health import check_memory_usage, check_disk_usage

logger = logging.getLogger(__name__)

# Create health check managers for each service
main_health = HealthCheck("juggernaut-main")
watchdog_health = HealthCheck("juggernaut-watchdog")
mcp_health = HealthCheck("juggernaut-mcp")
puppeteer_health = HealthCheck("juggernaut-puppeteer")

# Register common health checks for main service
@register_health_check(main_health)
async def check_db():
    return await check_database_connection()

@register_health_check(main_health)
async def check_workers():
    return await check_worker_registry()

@register_health_check(main_health)
async def check_memory():
    return await check_memory_usage()

@register_health_check(main_health)
async def check_disk():
    return await check_disk_usage()

# Register health checks for watchdog service
@register_health_check(watchdog_health)
async def watchdog_db():
    return await check_database_connection()

@register_health_check(watchdog_health)
async def watchdog_memory():
    return await check_memory_usage()

# Register health checks for MCP service
@register_health_check(mcp_health)
async def mcp_db():
    return await check_database_connection()

@register_health_check(mcp_health)
async def mcp_memory():
    return await check_memory_usage()

# Register health checks for Puppeteer service
@register_health_check(puppeteer_health)
async def puppeteer_memory():
    return await check_memory_usage()

@register_health_check(puppeteer_health)
async def puppeteer_disk():
    return await check_disk_usage()

def setup_health_endpoint(app: FastAPI, health_check: HealthCheck):
    """
    Set up health check endpoint for a FastAPI app.
    
    Args:
        app: FastAPI application
        health_check: HealthCheck instance to use
    """
    @app.get("/health")
    async def health_endpoint():
        """Health check endpoint for Railway."""
        result = await health_check.check()
        status_code = 200 if result["status"] == "healthy" else 503
        
        return JSONResponse(
            content=result,
            status_code=status_code
        )
    
    logger.info(f"Health check endpoint set up for {health_check.service_name}")

# Simple health check for non-FastAPI services
async def simple_health_check() -> Dict[str, Any]:
    """
    Simple health check for services without FastAPI.
    
    Returns:
        Health check result
    """
    return {
        "status": "healthy",
        "service": "juggernaut",
        "timestamp": datetime.now().isoformat()
    }

"""
Cost tracking and spending limits for JUGGERNAUT.

This module provides functions for tracking API costs and enforcing spending limits.
It uses a combination of database tracking and Redis-based rate limiting to ensure
that costs stay within budget.

Usage:
    from core.cost_tracker import CostTracker, track_api_cost
    
    # Track a cost
    await track_api_cost(
        service="openrouter",
        cost_usd=0.01,
        worker_id="EXECUTOR",
        request_id="123",
        details={"model": "gpt-4", "input_tokens": 100, "output_tokens": 50}
    )
    
    # Check if operation is within budget
    tracker = CostTracker()
    allowed, reason = await tracker.check_budget("openrouter", 0.05, "EXECUTOR")
    if not allowed:
        # Handle budget exceeded
        print(f"Operation not allowed: {reason}")
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from .database import query_db

logger = logging.getLogger(__name__)

# Default spending limits
DEFAULT_DAILY_LIMIT = 50.0  # $50 per day
DEFAULT_WEEKLY_LIMIT = 250.0  # $250 per week
DEFAULT_MONTHLY_LIMIT = 1000.0  # $1000 per month

# Service-specific limits
SERVICE_LIMITS = {
    "openrouter": {
        "daily": 20.0,
        "weekly": 100.0,
        "monthly": 400.0
    },
    "openai": {
        "daily": 15.0,
        "weekly": 75.0,
        "monthly": 300.0
    }
}

class BudgetExceededError(Exception):
    """Exception raised when a budget limit is exceeded."""
    pass

class CostTracker:
    """Tracks API costs and enforces spending limits."""
    
    def __init__(self, hard_limits_enabled: bool = True):
        """
        Initialize the cost tracker.
        
        Args:
            hard_limits_enabled: Whether to enforce hard spending limits
        """
        self.hard_limits_enabled = hard_limits_enabled
    
    async def track_cost(
        self,
        service: str,
        cost_usd: float,
        worker_id: str,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track an API cost.
        
        Args:
            service: Service name (e.g., "openrouter", "openai")
            cost_usd: Cost in USD
            worker_id: ID of the worker making the request
            request_id: Optional request ID for correlation
            details: Optional details about the request
            
        Returns:
            ID of the created cost record
            
        Raises:
            Exception: If cost tracking fails
        """
        try:
            # Insert cost record
            result = await query_db(
                """
                INSERT INTO api_cost_tracking (
                    service, cost_usd, worker_id, request_id, details
                ) VALUES (
                    $1, $2, $3, $4, $5
                )
                RETURNING id
                """,
                [service, cost_usd, worker_id, request_id, json.dumps(details) if details else None]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                logger.error(f"Failed to track cost for {service}")
                return None
            
            cost_id = str(result["rows"][0]["id"])
            
            # Update worker budget usage
            await self._update_worker_budget_usage(worker_id, cost_usd)
            
            return cost_id
        except Exception as e:
            logger.error(f"Failed to track cost: {e}")
            raise
    
    async def check_budget(
        self,
        service: str,
        estimated_cost: float,
        worker_id: str
    ) -> Tuple[bool, str]:
        """
        Check if an operation is within budget.
        
        Args:
            service: Service name
            estimated_cost: Estimated cost in USD
            worker_id: ID of the worker making the request
            
        Returns:
            Tuple of (allowed, reason)
        """
        if not self.hard_limits_enabled:
            return True, "Hard limits disabled"
        
        try:
            # Get worker budget
            budget = await self._get_worker_budget(worker_id)
            if not budget:
                # No budget found, use default limits
                daily_limit = DEFAULT_DAILY_LIMIT
                weekly_limit = DEFAULT_WEEKLY_LIMIT
                monthly_limit = DEFAULT_MONTHLY_LIMIT
                daily_usage = 0.0
                weekly_usage = 0.0
                monthly_usage = 0.0
            else:
                daily_limit = float(budget.get("daily_limit", DEFAULT_DAILY_LIMIT))
                weekly_limit = float(budget.get("weekly_limit", DEFAULT_WEEKLY_LIMIT))
                monthly_limit = float(budget.get("monthly_limit", DEFAULT_MONTHLY_LIMIT))
                daily_usage = float(budget.get("current_daily_usage", 0.0))
                weekly_usage = float(budget.get("current_weekly_usage", 0.0))
                monthly_usage = float(budget.get("current_monthly_usage", 0.0))
            
            # Check service-specific limits
            if service in SERVICE_LIMITS:
                service_daily_limit = SERVICE_LIMITS[service]["daily"]
                service_weekly_limit = SERVICE_LIMITS[service]["weekly"]
                service_monthly_limit = SERVICE_LIMITS[service]["monthly"]
                
                # Get service-specific usage
                service_usage = await self._get_service_usage(service)
                service_daily_usage = service_usage.get("daily", 0.0)
                service_weekly_usage = service_usage.get("weekly", 0.0)
                service_monthly_usage = service_usage.get("monthly", 0.0)
                
                # Check service-specific limits
                if service_daily_usage + estimated_cost > service_daily_limit:
                    return False, f"{service} daily limit exceeded: ${service_daily_usage:.2f} + ${estimated_cost:.2f} > ${service_daily_limit:.2f}"
                
                if service_weekly_usage + estimated_cost > service_weekly_limit:
                    return False, f"{service} weekly limit exceeded: ${service_weekly_usage:.2f} + ${estimated_cost:.2f} > ${service_weekly_limit:.2f}"
                
                if service_monthly_usage + estimated_cost > service_monthly_limit:
                    return False, f"{service} monthly limit exceeded: ${service_monthly_usage:.2f} + ${estimated_cost:.2f} > ${service_monthly_limit:.2f}"
            
            # Check worker budget limits
            if daily_usage + estimated_cost > daily_limit:
                return False, f"Daily budget exceeded: ${daily_usage:.2f} + ${estimated_cost:.2f} > ${daily_limit:.2f}"
            
            if weekly_usage + estimated_cost > weekly_limit:
                return False, f"Weekly budget exceeded: ${weekly_usage:.2f} + ${estimated_cost:.2f} > ${weekly_limit:.2f}"
            
            if monthly_usage + estimated_cost > monthly_limit:
                return False, f"Monthly budget exceeded: ${monthly_usage:.2f} + ${estimated_cost:.2f} > ${monthly_limit:.2f}"
            
            return True, "Within budget"
        except Exception as e:
            logger.error(f"Failed to check budget: {e}")
            # Allow the operation if budget check fails
            return True, f"Budget check failed: {e}"
    
    async def get_usage_report(self) -> Dict[str, Any]:
        """
        Get a usage report with current spending and limits.
        
        Returns:
            Dict with usage information
        """
        try:
            # Get overall usage
            overall_result = await query_db(
                """
                SELECT
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as daily_cost,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as weekly_cost,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as monthly_cost
                FROM api_cost_tracking
                """
            )
            
            overall = overall_result.get("rows", [{}])[0] if overall_result else {}
            
            # Get service-specific usage
            services_result = await query_db(
                """
                SELECT
                    service,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as daily_cost,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as weekly_cost,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as monthly_cost
                FROM api_cost_tracking
                GROUP BY service
                """
            )
            
            services = services_result.get("rows", []) if services_result else []
            
            # Get worker-specific usage
            workers_result = await query_db(
                """
                SELECT
                    worker_id,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as daily_cost,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as weekly_cost,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as monthly_cost
                FROM api_cost_tracking
                GROUP BY worker_id
                """
            )
            
            workers = workers_result.get("rows", []) if workers_result else []
            
            # Build report
            report = {
                "overall": {
                    "daily": float(overall.get("daily_cost") or 0.0),
                    "weekly": float(overall.get("weekly_cost") or 0.0),
                    "monthly": float(overall.get("monthly_cost") or 0.0),
                    "limits": {
                        "daily": DEFAULT_DAILY_LIMIT,
                        "weekly": DEFAULT_WEEKLY_LIMIT,
                        "monthly": DEFAULT_MONTHLY_LIMIT
                    }
                },
                "services": {},
                "workers": {}
            }
            
            # Add service-specific usage
            for service in services:
                service_name = service.get("service")
                if not service_name:
                    continue
                
                report["services"][service_name] = {
                    "daily": float(service.get("daily_cost") or 0.0),
                    "weekly": float(service.get("weekly_cost") or 0.0),
                    "monthly": float(service.get("monthly_cost") or 0.0),
                    "limits": SERVICE_LIMITS.get(service_name, {
                        "daily": DEFAULT_DAILY_LIMIT,
                        "weekly": DEFAULT_WEEKLY_LIMIT,
                        "monthly": DEFAULT_MONTHLY_LIMIT
                    })
                }
            
            # Add worker-specific usage
            for worker in workers:
                worker_id = worker.get("worker_id")
                if not worker_id:
                    continue
                
                budget = await self._get_worker_budget(worker_id)
                
                report["workers"][worker_id] = {
                    "daily": float(worker.get("daily_cost") or 0.0),
                    "weekly": float(worker.get("weekly_cost") or 0.0),
                    "monthly": float(worker.get("monthly_cost") or 0.0),
                    "limits": {
                        "daily": float(budget.get("daily_limit", DEFAULT_DAILY_LIMIT)) if budget else DEFAULT_DAILY_LIMIT,
                        "weekly": float(budget.get("weekly_limit", DEFAULT_WEEKLY_LIMIT)) if budget else DEFAULT_WEEKLY_LIMIT,
                        "monthly": float(budget.get("monthly_limit", DEFAULT_MONTHLY_LIMIT)) if budget else DEFAULT_MONTHLY_LIMIT
                    }
                }
            
            return report
        except Exception as e:
            logger.error(f"Failed to get usage report: {e}")
            return {
                "error": str(e),
                "overall": {
                    "daily": 0.0,
                    "weekly": 0.0,
                    "monthly": 0.0
                }
            }
    
    async def _get_worker_budget(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a worker's budget information.
        
        Args:
            worker_id: ID of the worker
            
        Returns:
            Dict with budget information or None if not found
        """
        try:
            result = await query_db(
                """
                SELECT * FROM worker_budgets
                WHERE worker_id = $1
                """,
                [worker_id]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                return None
            
            return result["rows"][0]
        except Exception as e:
            logger.error(f"Failed to get worker budget: {e}")
            return None
    
    async def _update_worker_budget_usage(self, worker_id: str, cost_usd: float) -> bool:
        """
        Update a worker's budget usage.
        
        Args:
            worker_id: ID of the worker
            cost_usd: Cost to add to usage
            
        Returns:
            True if update was successful
        """
        try:
            # Check if worker budget exists
            budget = await self._get_worker_budget(worker_id)
            
            if budget:
                # Update existing budget
                result = await query_db(
                    """
                    UPDATE worker_budgets
                    SET
                        current_daily_usage = current_daily_usage + $1,
                        current_weekly_usage = current_weekly_usage + $1,
                        current_monthly_usage = current_monthly_usage + $1,
                        updated_at = NOW()
                    WHERE worker_id = $2
                    """,
                    [cost_usd, worker_id]
                )
                
                return bool(result and result.get("rowCount", 0) > 0)
            else:
                # Create new budget
                result = await query_db(
                    """
                    INSERT INTO worker_budgets (
                        worker_id,
                        daily_limit,
                        weekly_limit,
                        monthly_limit,
                        current_daily_usage,
                        current_weekly_usage,
                        current_monthly_usage
                    ) VALUES (
                        $1, $2, $3, $4, $5, $5, $5
                    )
                    """,
                    [worker_id, DEFAULT_DAILY_LIMIT, DEFAULT_WEEKLY_LIMIT, DEFAULT_MONTHLY_LIMIT, cost_usd]
                )
                
                return bool(result and result.get("rowCount", 0) > 0)
        except Exception as e:
            logger.error(f"Failed to update worker budget usage: {e}")
            return False
    
    async def _get_service_usage(self, service: str) -> Dict[str, float]:
        """
        Get usage for a specific service.
        
        Args:
            service: Service name
            
        Returns:
            Dict with daily, weekly, and monthly usage
        """
        try:
            result = await query_db(
                """
                SELECT
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as daily_cost,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as weekly_cost,
                    SUM(cost_usd) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as monthly_cost
                FROM api_cost_tracking
                WHERE service = $1
                """,
                [service]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                return {"daily": 0.0, "weekly": 0.0, "monthly": 0.0}
            
            row = result["rows"][0]
            
            return {
                "daily": float(row.get("daily_cost") or 0.0),
                "weekly": float(row.get("weekly_cost") or 0.0),
                "monthly": float(row.get("monthly_cost") or 0.0)
            }
        except Exception as e:
            logger.error(f"Failed to get service usage: {e}")
            return {"daily": 0.0, "weekly": 0.0, "monthly": 0.0}
    
    async def reset_daily_usage(self) -> bool:
        """
        Reset daily usage for all workers.
        
        Returns:
            True if reset was successful
        """
        try:
            result = await query_db(
                """
                UPDATE worker_budgets
                SET
                    current_daily_usage = 0,
                    last_reset_daily = NOW()
                """
            )
            
            return bool(result and result.get("rowCount", 0) > 0)
        except Exception as e:
            logger.error(f"Failed to reset daily usage: {e}")
            return False
    
    async def reset_weekly_usage(self) -> bool:
        """
        Reset weekly usage for all workers.
        
        Returns:
            True if reset was successful
        """
        try:
            result = await query_db(
                """
                UPDATE worker_budgets
                SET
                    current_weekly_usage = 0,
                    last_reset_weekly = NOW()
                """
            )
            
            return bool(result and result.get("rowCount", 0) > 0)
        except Exception as e:
            logger.error(f"Failed to reset weekly usage: {e}")
            return False
    
    async def reset_monthly_usage(self) -> bool:
        """
        Reset monthly usage for all workers.
        
        Returns:
            True if reset was successful
        """
        try:
            result = await query_db(
                """
                UPDATE worker_budgets
                SET
                    current_monthly_usage = 0,
                    last_reset_monthly = NOW()
                """
            )
            
            return bool(result and result.get("rowCount", 0) > 0)
        except Exception as e:
            logger.error(f"Failed to reset monthly usage: {e}")
            return False

# Convenience function for tracking API costs
async def track_api_cost(
    service: str,
    cost_usd: float,
    worker_id: str,
    request_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """
    Track an API cost.
    
    Args:
        service: Service name (e.g., "openrouter", "openai")
        cost_usd: Cost in USD
        worker_id: ID of the worker making the request
        request_id: Optional request ID for correlation
        details: Optional details about the request
        
    Returns:
        ID of the created cost record
    """
    tracker = CostTracker()
    return await tracker.track_cost(service, cost_usd, worker_id, request_id, details)

# Convenience function for checking budget
async def check_budget(
    service: str,
    estimated_cost: float,
    worker_id: str
) -> Tuple[bool, str]:
    """
    Check if an operation is within budget.
    
    Args:
        service: Service name
        estimated_cost: Estimated cost in USD
        worker_id: ID of the worker making the request
        
    Returns:
        Tuple of (allowed, reason)
    """
    tracker = CostTracker()
    return await tracker.check_budget(service, estimated_cost, worker_id)

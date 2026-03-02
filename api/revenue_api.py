"""
Revenue API Service - Expose revenue tracking data and service endpoints.

Features:
- API endpoints for revenue analytics
- Self-service provisioning
- Tiered access controls
- Usage monitoring
- Health checks

Standard Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history  
- GET /revenue/charts - Revenue over time data

Service Endpoints:  
- POST /revenue/service - Provision new service instance
- GET /revenue/service/{id} - Get service status
- GET /revenue/service/limits - Check usage limits
"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from core.database import query_db
from core.limiter import check_rate_limit, record_api_call


class ServiceTier(Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class ServiceInstance:
    id: str
    owner_id: str
    tier: ServiceTier  
    created_at: datetime
    last_active: datetime
    monthly_calls: int
    api_key: str
    rate_limit: int  # Calls per minute
    is_active: bool


def _validate_service_request(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate service provisioning request."""
    if not data.get("owner_id"):
        return False, "Missing owner_id"
    if not data.get("tier") or data["tier"] not in [t.value for t in ServiceTier]:
        return False, "Invalid tier"
    return True, ""


def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message})


async def handle_revenue_summary(service_id: Optional[str] = None) -> Dict[str, Any]:
    """Get MTD/QTD/YTD revenue totals."""
    if service_id:
        limit_reached, _ = await check_rate_limit("revenue_summary", service_id)
        if limit_reached:
            return _error_response(429, "Rate limit exceeded")
    try:
        now = datetime.now(timezone.utc)
        
        # Calculate period boundaries
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        quarter_start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get revenue by period
        sql = f"""
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost_cents,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) - 
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as net_profit_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count,
            MIN(recorded_at) FILTER (WHERE event_type = 'revenue') as first_revenue_at,
            MAX(recorded_at) FILTER (WHERE event_type = 'revenue') as last_revenue_at
        FROM revenue_events
        WHERE recorded_at >= '{month_start.isoformat()}'
        """
        
        mtd_result = await query_db(sql.replace(month_start.isoformat(), month_start.isoformat()))
        mtd = mtd_result.get("rows", [{}])[0]
        
        qtd_result = await query_db(sql.replace(month_start.isoformat(), quarter_start.isoformat()))
        qtd = qtd_result.get("rows", [{}])[0]
        
        ytd_result = await query_db(sql.replace(month_start.isoformat(), year_start.isoformat()))
        ytd = ytd_result.get("rows", [{}])[0]
        
        # All-time totals
        all_time_sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost_cents,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) - 
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as net_profit_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
        FROM revenue_events
        """
        
        all_time_result = await query_db(all_time_sql)
        all_time = all_time_result.get("rows", [{}])[0]
        
        return _make_response(200, {
            "mtd": {
                "revenue_cents": mtd.get("total_revenue_cents") or 0,
                "cost_cents": mtd.get("total_cost_cents") or 0,
                "profit_cents": mtd.get("net_profit_cents") or 0,
                "transaction_count": mtd.get("transaction_count") or 0,
                "first_revenue_at": mtd.get("first_revenue_at"),
                "last_revenue_at": mtd.get("last_revenue_at")
            },
            "qtd": {
                "revenue_cents": qtd.get("total_revenue_cents") or 0,
                "cost_cents": qtd.get("total_cost_cents") or 0,
                "profit_cents": qtd.get("net_profit_cents") or 0,
                "transaction_count": qtd.get("transaction_count") or 0
            },
            "ytd": {
                "revenue_cents": ytd.get("total_revenue_cents") or 0,
                "cost_cents": ytd.get("total_cost_cents") or 0,
                "profit_cents": ytd.get("net_profit_cents") or 0,
                "transaction_count": ytd.get("transaction_count") or 0
            },
            "all_time": {
                "revenue_cents": all_time.get("total_revenue_cents") or 0,
                "cost_cents": all_time.get("total_cost_cents") or 0,
                "profit_cents": all_time.get("net_profit_cents") or 0,
                "transaction_count": all_time.get("transaction_count") or 0
            }
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch revenue summary: {str(e)}")


async def handle_revenue_transactions(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Get transaction history with pagination."""
    try:
        limit = int(query_params.get("limit", ["50"])[0] if isinstance(query_params.get("limit"), list) else query_params.get("limit", 50))
        offset = int(query_params.get("offset", ["0"])[0] if isinstance(query_params.get("offset"), list) else query_params.get("offset", 0))
        event_type = query_params.get("event_type", [""])[0] if isinstance(query_params.get("event_type"), list) else query_params.get("event_type", "")
        
        where_clause = ""
        if event_type:
            where_clause = f"WHERE event_type = '{event_type}'"
        
        sql = f"""
        SELECT 
            id,
            experiment_id,
            event_type,
            amount_cents,
            currency,
            source,
            metadata,
            recorded_at,
            created_at
        FROM revenue_events
        {where_clause}
        ORDER BY recorded_at DESC
        LIMIT {limit}
        OFFSET {offset}
        """
        
        result = await query_db(sql)
        transactions = result.get("rows", [])
        
        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM revenue_events {where_clause}"
        count_result = await query_db(count_sql)
        total = count_result.get("rows", [{}])[0].get("total", 0)
        
        return _make_response(200, {
            "transactions": transactions,
            "total": total,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch transactions: {str(e)}")


async def handle_revenue_charts(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Get revenue over time for charts."""
    try:
        days = int(query_params.get("days", ["30"])[0] if isinstance(query_params.get("days"), list) else query_params.get("days", 30))
        
        # Daily revenue for the last N days
        sql = f"""
        SELECT 
            DATE(recorded_at) as date,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) - 
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as profit_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        GROUP BY DATE(recorded_at)
        ORDER BY date DESC
        """
        
        result = await query_db(sql)
        daily_data = result.get("rows", [])
        
        # By source
        source_sql = f"""
        SELECT 
            source,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        GROUP BY source
        ORDER BY revenue_cents DESC
        """
        
        source_result = await query_db(source_sql)
        by_source = source_result.get("rows", [])
        
        return _make_response(200, {
            "daily": daily_data,
            "by_source": by_source,
            "period_days": days
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch chart data: {str(e)}")


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route revenue API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # GET /revenue/summary
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "summary" and method == "GET":
        return handle_revenue_summary()
    
    # GET /revenue/transactions
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "transactions" and method == "GET":
        return handle_revenue_transactions(query_params)
    
    # GET /revenue/charts
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "charts" and method == "GET":
        return handle_revenue_charts(query_params)
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
"""
Revenue Service Provisioning - Handle automated onboarding and management 
of revenue service instances.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.database import query_db
from .revenue_api import ServiceTier, ServiceInstance, _validate_service_request


def provision_service(execute_sql: callable, data: Dict[str, Any]) -> Dict[str, Any]:
    """Provision new revenue service instance."""
    # Validate request
    is_valid, msg = _validate_service_request(data)
    if not is_valid:
        return {
            "success": False,
            "error": msg,
            "status_code": 400
        }

    # Generate API key
    api_key = str(uuid.uuid4())
    hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Set defaults based on tier
    tier = ServiceTier(data["tier"])
    rate_limit = {
        ServiceTier.FREE: 120,
        ServiceTier.BASIC: 1000,
        ServiceTier.PRO: 5000,
        ServiceTier.ENTERPRISE: 25000
    }[tier]

    try:
        execute_sql(
            f"""
            INSERT INTO revenue_services (
                id, owner_id, tier, created_at, 
                last_active, api_key_hash, rate_limit,  
                monthly_calls, is_active
            ) VALUES (
                gen_random_uuid(),
                '{data['owner_id']}',
                '{tier.value}',
                NOW(),
                NOW(),
                '{hashed_key}',
                {rate_limit},
                0,
                TRUE
            )
            RETURNING id
            """
        )
        return {
            "success": True,
            "api_key": api_key,
            "tier": tier.value,
            "rate_limit": rate_limit
        }
    except Exception as e:
        return {
            "success": False, 
            "error": str(e),
            "status_code": 500
        }


def get_service_status(execute_sql: callable, service_id: str) -> Optional[ServiceInstance]:
    """Get current status of a service instance."""
    try:
        res = execute_sql(
            f"""
            SELECT 
                id, owner_id, tier, created_at, last_active,
                api_key_hash, rate_limit, monthly_calls, is_active
            FROM revenue_services
            WHERE id = '{service_id}'
            """
        )
        row = res.get("rows", [{}])[0]
        
        last_active = row["last_active"].isoformat() if row["last_active"] else None
        
        return ServiceInstance(
            id=row["id"],
            owner_id=row["owner_id"],
            tier=ServiceTier(row["tier"]),
            created_at=row["created_at"],
            last_active=row["last_active"],
            monthly_calls=row["monthly_calls"],
            api_key=row["api_key_hash"],
            rate_limit=row["rate_limit"],
            is_active=row["is_active"]
        )
    except Exception:
        return None


def check_service_limits(execute_sql: callable, service_id: str) -> Dict[str, Any]:
    """Check usage against tier limits."""
    service = get_service_status(execute_sql, service_id)
    if not service:
        return {"error": "Service not found"}

    return {
        "tier": service.tier.value,
        "rate_limit": service.rate_limit,
        "monthly_calls": service.monthly_calls,
        "current_month": datetime.now(timezone.utc).strftime("%Y-%m")
    }


def record_usage(execute_sql: callable, service_id: str) -> None:
    """Record API usage."""
    try:
        execute_sql(
            f"""
            UPDATE revenue_services
            SET 
                monthly_calls = monthly_calls + 1,
                last_active = NOW()
            WHERE id = '{service_id}'
            """
        )
    except Exception:
        pass

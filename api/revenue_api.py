"""
Revenue API - Expose revenue tracking data to Spartan HQ.

Endpoints:
- GET /revenue/summary - MTD/QTD/YTD totals
- GET /revenue/transactions - Transaction history
- GET /revenue/charts - Revenue over time data
- POST /revenue/payments - Process payments
- POST /revenue/provision - Provision services
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.database import query_db
from .revenue_service import RevenueService, PaymentProcessor

revenue_service = RevenueService()


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


async def handle_revenue_summary() -> Dict[str, Any]:
    """Get MTD/QTD/YTD revenue totals."""
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


async def handle_payment_processing(body: Dict[str, Any]) -> Dict[str, Any]:
    """Process a payment."""
    try:
        amount_cents = int(body.get("amount_cents", 0))
        currency = body.get("currency", "USD")
        payment_method = body.get("payment_method", {})
        processor = PaymentProcessor[body.get("processor", "STRIPE")]
        
        success, payment_id = await revenue_service.process_payment(
            amount_cents=amount_cents,
            currency=currency,
            payment_method=payment_method,
            processor=processor
        )
        
        if not success:
            return _error_response(400, f"Payment failed: {payment_id}")
            
        return _make_response(200, {
            "success": True,
            "payment_id": payment_id,
            "amount_cents": amount_cents,
            "currency": currency
        })
        
    except Exception as e:
        return _error_response(500, f"Payment processing error: {str(e)}")

async def handle_service_provisioning(body: Dict[str, Any]) -> Dict[str, Any]:
    """Provision a service."""
    try:
        plan_id = body.get("plan_id")
        customer_id = body.get("customer_id")
        
        if not plan_id or not customer_id:
            return _error_response(400, "Missing plan_id or customer_id")
            
        success, service_id = await revenue_service.provision_service(
            plan_id=plan_id,
            customer_id=customer_id
        )
        
        if not success:
            return _error_response(400, f"Service provisioning failed: {service_id}")
            
        return _make_response(200, {
            "success": True,
            "service_id": service_id,
            "plan_id": plan_id,
            "customer_id": customer_id
        })
        
    except Exception as e:
        return _error_response(500, f"Service provisioning error: {str(e)}")

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
    
    # POST /revenue/payments
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "payments" and method == "POST":
        if not body:
            return _error_response(400, "Missing request body")
        try:
            body_data = json.loads(body)
            return handle_payment_processing(body_data)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON body")
    
    # POST /revenue/provision
    if len(parts) == 2 and parts[0] == "revenue" and parts[1] == "provision" and method == "POST":
        if not body:
            return _error_response(400, "Missing request body")
        try:
            body_data = json.loads(body)
            return handle_service_provisioning(body_data)
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON body")
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
"""
Revenue Service Core - Handles billing, payments, and service delivery.

Features:
- Payment processor integrations
- Automated billing cycles
- Service provisioning
- Transaction logging
- Circuit breakers
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from enum import Enum, auto

from core.database import query_db

logger = logging.getLogger(__name__)

class PaymentProcessor(Enum):
    STRIPE = auto()
    PAYPAL = auto()
    BRAINTREE = auto()

class RevenueService:
    """Core revenue generation service."""
    
    def __init__(self):
        self.circuit_breaker_state = "closed"
        self.last_failure_time = None
        self.failure_count = 0
        
    async def process_payment(self, amount_cents: int, currency: str, payment_method: Dict[str, Any], 
                            processor: PaymentProcessor = PaymentProcessor.STRIPE) -> Tuple[bool, Optional[str]]:
        """Process a payment through the selected processor."""
        if self.circuit_breaker_state == "open":
            return False, "Circuit breaker open - payments temporarily disabled"
            
        try:
            # Process payment through selected processor
            payment_id = await self._call_processor(processor, amount_cents, currency, payment_method)
            
            # Log successful transaction
            await self._log_transaction(
                event_type="revenue",
                amount_cents=amount_cents,
                currency=currency,
                source=f"{processor.name.lower()}_payment",
                metadata={
                    "payment_id": payment_id,
                    "processor": processor.name,
                    "method": payment_method.get("type")
                }
            )
            
            return True, payment_id
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            self._handle_failure()
            return False, str(e)
            
    async def _call_processor(self, processor: PaymentProcessor, amount_cents: int, 
                            currency: str, payment_method: Dict[str, Any]) -> str:
        """Call the actual payment processor API."""
        # Implementation would integrate with real payment processors
        # This is a mock implementation
        return f"pmt_{datetime.now(timezone.utc).timestamp()}"
        
    async def _log_transaction(self, event_type: str, amount_cents: int, currency: str,
                             source: str, metadata: Dict[str, Any]) -> None:
        """Log revenue transaction to database."""
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
                {amount_cents},
                '{currency}',
                '{source}',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
    def _handle_failure(self) -> None:
        """Handle failure and manage circuit breaker state."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count > 10:
            self.circuit_breaker_state = "open"
            logger.warning("Circuit breaker opened due to excessive failures")
            
    def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker to closed state."""
        self.circuit_breaker_state = "closed"
        self.failure_count = 0
        self.last_failure_time = None
        logger.info("Circuit breaker reset to closed state")
        
    async def provision_service(self, plan_id: str, customer_id: str) -> Tuple[bool, Optional[str]]:
        """Provision a service based on the selected plan."""
        try:
            # Implementation would provision actual services
            # This is a mock implementation
            service_id = f"svc_{datetime.now(timezone.utc).timestamp()}"
            
            await self._log_transaction(
                event_type="provision",
                amount_cents=0,
                currency="USD",
                source="service_provisioning",
                metadata={
                    "plan_id": plan_id,
                    "customer_id": customer_id,
                    "service_id": service_id
                }
            )
            
            return True, service_id
            
        except Exception as e:
            logger.error(f"Service provisioning failed: {str(e)}")
            return False, str(e)

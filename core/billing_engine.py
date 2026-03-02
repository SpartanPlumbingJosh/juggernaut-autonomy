"""
Automated SaaS Billing Engine

Features:
- Subscription management
- Usage-based billing
- Payment processing
- Rate limiting
- Failover mechanisms
- Self-monitoring
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Subscription:
    id: str
    customer_id: str
    plan_id: str
    status: str  # active, canceled, paused
    billing_cycle: str  # monthly, annual
    next_billing_date: datetime
    usage_limits: Dict[str, int]
    current_usage: Dict[str, int]

@dataclass
class Invoice:
    id: str
    subscription_id: str
    amount_due: float
    currency: str
    period_start: datetime
    period_end: datetime
    status: str  # draft, open, paid, void

class BillingEngine:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.rate_limit = 100  # Max operations per minute
        self.last_operation_time = time.time()
        self.failover_mode = False
        
    def _check_rate_limit(self) -> bool:
        """Enforce rate limiting to prevent API abuse."""
        current_time = time.time()
        if current_time - self.last_operation_time < 60/self.rate_limit:
            return False
        self.last_operation_time = current_time
        return True
        
    def _log_failure(self, operation: str, error: str):
        """Log failures and trigger failover if needed."""
        logger.error(f"Operation {operation} failed: {error}")
        self.log_action(
            "billing.failure",
            f"Billing operation failed: {operation}",
            level="error",
            error_data={"operation": operation, "error": error}
        )
        
        # If we have multiple failures, enter failover mode
        if self._get_recent_failures() > 3:
            self.failover_mode = True
            logger.warning("Entering failover mode")
            
    def _get_recent_failures(self) -> int:
        """Count recent failures for failover decision making."""
        try:
            res = self.execute_sql(
                """
                SELECT COUNT(*) as failures
                FROM billing_logs
                WHERE level = 'error'
                AND created_at > NOW() - INTERVAL '5 minutes'
                """
            )
            return res.get("rows", [{}])[0].get("failures", 0)
        except Exception:
            return 0
            
    def _process_payment(self, invoice: Invoice) -> bool:
        """Process payment with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Simulate payment processing
                if random.random() < 0.9:  # 90% success rate
                    return True
                raise Exception("Payment processing failed")
            except Exception as e:
                if attempt == max_retries - 1:
                    self._log_failure("process_payment", str(e))
                    return False
                time.sleep(2 ** attempt)  # Exponential backoff
        return False
        
    def generate_invoices(self) -> List[Invoice]:
        """Generate invoices for subscriptions due for billing."""
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded")
            return []
            
        try:
            # Get subscriptions due for billing
            res = self.execute_sql(
                """
                SELECT * FROM subscriptions
                WHERE status = 'active'
                AND next_billing_date <= NOW()
                LIMIT 100
                """
            )
            subscriptions = [Subscription(**row) for row in res.get("rows", [])]
            
            invoices = []
            for sub in subscriptions:
                # Calculate usage and charges
                invoice = self._create_invoice(sub)
                if self._process_payment(invoice):
                    invoices.append(invoice)
                    self._update_subscription(sub)
                    
            return invoices
            
        except Exception as e:
            self._log_failure("generate_invoices", str(e))
            return []
            
    def _create_invoice(self, subscription: Subscription) -> Invoice:
        """Create invoice for a subscription."""
        # Calculate charges based on usage and plan
        return Invoice(
            id=f"inv_{int(time.time())}",
            subscription_id=subscription.id,
            amount_due=100.0,  # Simplified for example
            currency="USD",
            period_start=subscription.next_billing_date - timedelta(days=30),
            period_end=subscription.next_billing_date,
            status="open"
        )
        
    def _update_subscription(self, subscription: Subscription):
        """Update subscription after successful billing."""
        try:
            self.execute_sql(
                f"""
                UPDATE subscriptions
                SET next_billing_date = NOW() + INTERVAL '1 month',
                    current_usage = '{{}}'::jsonb
                WHERE id = '{subscription.id}'
                """
            )
        except Exception as e:
            self._log_failure("update_subscription", str(e))
            
    def monitor_system(self) -> Dict[str, Any]:
        """Monitor billing system health."""
        try:
            stats = {
                "active_subscriptions": self._count_active_subscriptions(),
                "pending_invoices": self._count_pending_invoices(),
                "recent_failures": self._get_recent_failures(),
                "failover_mode": self.failover_mode,
                "rate_limit": self.rate_limit
            }
            self.log_action(
                "billing.monitor",
                "Billing system health check",
                level="info",
                output_data=stats
            )
            return stats
        except Exception as e:
            self._log_failure("monitor_system", str(e))
            return {}
            
    def _count_active_subscriptions(self) -> int:
        """Count active subscriptions."""
        try:
            res = self.execute_sql(
                """
                SELECT COUNT(*) as count
                FROM subscriptions
                WHERE status = 'active'
                """
            )
            return res.get("rows", [{}])[0].get("count", 0)
        except Exception:
            return 0
            
    def _count_pending_invoices(self) -> int:
        """Count pending invoices."""
        try:
            res = self.execute_sql(
                """
                SELECT COUNT(*) as count
                FROM invoices
                WHERE status = 'open'
                """
            )
            return res.get("rows", [{}])[0].get("count", 0)
        except Exception:
            return 0

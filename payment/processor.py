from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json
from enum import Enum

class PaymentType(Enum):
    SUBSCRIPTION = "subscription"
    USAGE = "usage"
    ONE_TIME = "one_time"

class PaymentStatus(Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentProcessor:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action

    async def create_payment_intent(self, amount_cents: int, currency: str, payment_type: PaymentType, 
                                  customer_id: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a payment intent for a customer"""
        payment_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata or {})
        
        try:
            self.execute_sql(f"""
                INSERT INTO payments (
                    id, amount_cents, currency, payment_type,
                    status, customer_id, metadata, created_at
                ) VALUES (
                    '{payment_id}', {amount_cents}, '{currency}', '{payment_type.value}',
                    '{PaymentStatus.PENDING.value}', '{customer_id}', '{metadata_json}', NOW()
                )
            """)
            return {"success": True, "payment_id": payment_id}
        except Exception as e:
            self.log_action("payment.create_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, event_type: str, event_data: Dict) -> Dict[str, Any]:
        """Process payment webhook events"""
        payment_id = event_data.get("payment_id")
        if not payment_id:
            return {"success": False, "error": "Missing payment_id"}
            
        if event_type == "payment.succeeded":
            return await self._mark_payment_succeeded(payment_id)
        elif event_type == "payment.failed":
            return await self._mark_payment_failed(payment_id)
        elif event_type == "payment.refunded":
            return await self._mark_payment_refunded(payment_id)
        else:
            return {"success": False, "error": f"Unknown event type: {event_type}"}

    async def _mark_payment_succeeded(self, payment_id: str) -> Dict[str, Any]:
        """Mark payment as succeeded and record revenue"""
        try:
            # Get payment details
            res = self.execute_sql(f"""
                SELECT amount_cents, currency, customer_id, metadata
                FROM payments
                WHERE id = '{payment_id}'
            """)
            payment = res.get("rows", [{}])[0]
            
            # Record revenue event
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, amount_cents, currency, event_type,
                    source, metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(), {payment['amount_cents']}, '{payment['currency']}', 'revenue',
                    'payment', '{payment['metadata']}', NOW()
                )
            """)
            
            # Update payment status
            self.execute_sql(f"""
                UPDATE payments
                SET status = '{PaymentStatus.SUCCEEDED.value}',
                    succeeded_at = NOW()
                WHERE id = '{payment_id}'
            """)
            
            return {"success": True}
        except Exception as e:
            self.log_action("payment.webhook_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

    async def generate_invoice(self, payment_id: str) -> Dict[str, Any]:
        """Generate invoice for a payment"""
        # Implementation would generate PDF and store it
        return {"success": True, "invoice_url": f"https://invoices.example.com/{payment_id}"}

    async def handle_dunning(self, failed_payment_id: str) -> Dict[str, Any]:
        """Handle failed payment retry logic"""
        # Implementation would retry payment and notify customer
        return {"success": True}

    async def get_payment_history(self, customer_id: str) -> List[Dict]:
        """Get payment history for a customer"""
        res = self.execute_sql(f"""
            SELECT id, amount_cents, currency, payment_type, status,
                   created_at, succeeded_at, metadata
            FROM payments
            WHERE customer_id = '{customer_id}'
            ORDER BY created_at DESC
        """)
        return res.get("rows", [])

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel an active subscription"""
        try:
            self.execute_sql(f"""
                UPDATE subscriptions
                SET status = 'canceled',
                    canceled_at = NOW()
                WHERE id = '{subscription_id}'
            """)
            return {"success": True}
        except Exception as e:
            self.log_action("subscription.cancel_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

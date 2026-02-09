from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

from core.database import execute_sql

class BillingService:
    """Handles automated billing and service delivery."""
    
    def __init__(self):
        self.base_price_cents = 9900  # $99/month base price
        self.currency = "USD"
        
    async def create_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Create a new subscription."""
        subscription_id = str(uuid.uuid4())
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30)
        
        await execute_sql(
            f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id,
                status, start_date, end_date,
                created_at, updated_at
            ) VALUES (
                '{subscription_id}', '{customer_id}', '{plan_id}',
                'active', '{start_date.isoformat()}', '{end_date.isoformat()}',
                NOW(), NOW()
            )
            """
        )
        
        # Create initial invoice
        await self.create_invoice(subscription_id)
        
        return {
            "subscription_id": subscription_id,
            "status": "active",
            "start_date": start_date,
            "end_date": end_date
        }
        
    async def create_invoice(self, subscription_id: str) -> Dict[str, Any]:
        """Create an invoice for a subscription."""
        invoice_id = str(uuid.uuid4())
        amount_cents = self.base_price_cents
        due_date = datetime.utcnow() + timedelta(days=7)
        
        await execute_sql(
            f"""
            INSERT INTO invoices (
                id, subscription_id, amount_cents,
                currency, status, due_date,
                created_at, updated_at
            ) VALUES (
                '{invoice_id}', '{subscription_id}', {amount_cents},
                '{self.currency}', 'pending', '{due_date.isoformat()}',
                NOW(), NOW()
            )
            """
        )
        
        # Record revenue event
        await self.record_revenue_event(
            event_type="invoice",
            amount_cents=amount_cents,
            currency=self.currency,
            source="subscription",
            metadata={
                "invoice_id": invoice_id,
                "subscription_id": subscription_id
            }
        )
        
        return {
            "invoice_id": invoice_id,
            "amount_cents": amount_cents,
            "due_date": due_date,
            "status": "pending"
        }
        
    async def record_revenue_event(
        self,
        event_type: str,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Record a revenue event."""
        event_id = str(uuid.uuid4())
        recorded_at = datetime.utcnow()
        
        await execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents,
                currency, source, metadata,
                recorded_at, created_at
            ) VALUES (
                '{event_id}', '{event_type}', {amount_cents},
                '{currency}', '{source}', '{json.dumps(metadata or {})}',
                '{recorded_at.isoformat()}', NOW()
            )
            """
        )
        
        return {
            "event_id": event_id,
            "recorded_at": recorded_at,
            "status": "recorded"
        }
        
    async def process_payment(self, invoice_id: str, payment_method: str) -> Dict[str, Any]:
        """Process payment for an invoice."""
        # Mark invoice as paid
        await execute_sql(
            f"""
            UPDATE invoices
            SET status = 'paid',
                payment_method = '{payment_method}',
                paid_at = NOW(),
                updated_at = NOW()
            WHERE id = '{invoice_id}'
            """
        )
        
        # Record payment event
        await self.record_revenue_event(
            event_type="payment",
            amount_cents=self.base_price_cents,
            currency=self.currency,
            source="subscription",
            metadata={
                "invoice_id": invoice_id,
                "payment_method": payment_method
            }
        )
        
        return {
            "invoice_id": invoice_id,
            "status": "paid",
            "payment_method": payment_method
        }

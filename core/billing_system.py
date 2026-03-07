"""
Automated Billing System - Handles invoicing, payment processing, and revenue tracking.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

class BillingSystem:
    """Core billing system for handling subscriptions and payments."""
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    async def create_invoice(self, customer_id: str, amount_cents: int, 
                           description: str, due_date: Optional[datetime] = None) -> Dict:
        """Create a new invoice for a customer."""
        invoice_id = str(uuid.uuid4())
        due_date = due_date or datetime.utcnow() + timedelta(days=30)
        
        await self.execute_sql(
            f"""
            INSERT INTO invoices (
                id, customer_id, amount_cents, description, 
                status, created_at, due_date
            ) VALUES (
                '{invoice_id}', '{customer_id}', {amount_cents}, 
                '{description.replace("'", "''")}', 'pending',
                NOW(), '{due_date.isoformat()}'
            )
            """
        )
        
        await self.log_action(
            "billing.invoice_created",
            f"Invoice created for {customer_id}",
            level="info",
            output_data={"invoice_id": invoice_id, "amount_cents": amount_cents}
        )
        
        return {"success": True, "invoice_id": invoice_id}
        
    async def process_payment(self, invoice_id: str, payment_method: str,
                            amount_cents: int) -> Dict:
        """Process payment for an invoice."""
        # Payment processing logic would integrate with payment gateway here
        await self.execute_sql(
            f"""
            UPDATE invoices
            SET status = 'paid',
                paid_at = NOW()
            WHERE id = '{invoice_id}'
            """
        )
        
        await self.log_action(
            "billing.payment_processed",
            f"Payment processed for invoice {invoice_id}",
            level="info",
            output_data={"invoice_id": invoice_id, "amount_cents": amount_cents}
        )
        
        # Record revenue event
        await self.execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, source,
                recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), 'revenue', {amount_cents},
                'payment', NOW(), NOW()
            )
            """
        )
        
        return {"success": True}
        
    async def get_outstanding_invoices(self, customer_id: str) -> List[Dict]:
        """Get all unpaid invoices for a customer."""
        result = await self.execute_sql(
            f"""
            SELECT id, amount_cents, description, due_date
            FROM invoices
            WHERE customer_id = '{customer_id}'
              AND status = 'pending'
            ORDER BY due_date ASC
            """
        )
        return result.get("rows", [])

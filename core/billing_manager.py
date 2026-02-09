"""
Billing Manager - Handles subscription management, invoicing, and revenue tracking.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from decimal import Decimal

class BillingManager:
    def __init__(self, db_executor: Any):
        self.db_executor = db_executor
        
    async def create_invoice(self, customer_id: str, amount: Decimal, currency: str,
                           description: str, due_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Create and store a new invoice."""
        try:
            invoice_data = {
                "customer_id": customer_id,
                "amount": float(amount),
                "currency": currency,
                "description": description,
                "status": "pending",
                "due_date": due_date or (datetime.utcnow() + timedelta(days=30)),
                "created_at": datetime.utcnow()
            }
            
            # Store invoice in database
            await self.db_executor(
                f"""
                INSERT INTO invoices (
                    id, customer_id, amount, currency, description,
                    status, due_date, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{invoice_data['customer_id']}',
                    {invoice_data['amount']},
                    '{invoice_data['currency']}',
                    '{invoice_data['description']}',
                    '{invoice_data['status']}',
                    '{invoice_data['due_date'].isoformat()}',
                    '{invoice_data['created_at'].isoformat()}'
                )
                RETURNING id
                """
            )
            
            return {"success": True, "invoice_id": invoice_data['id']}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def process_payment(self, invoice_id: str, payment_method: str,
                            amount: Decimal) -> Dict[str, Any]:
        """Process payment for an invoice."""
        try:
            # Mark invoice as paid
            await self.db_executor(
                f"""
                UPDATE invoices
                SET status = 'paid',
                    paid_at = NOW(),
                    payment_method = '{payment_method}'
                WHERE id = '{invoice_id}'
                """
            )
            
            # Record revenue event
            await self.db_executor(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(amount * 100)},
                    'USD',
                    'payment',
                    '{{"invoice_id": "{invoice_id}"}}'::jsonb,
                    NOW()
                )
                """
            )
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def generate_monthly_statements(self) -> Dict[str, Any]:
        """Generate monthly billing statements for all active customers."""
        try:
            # Get all active subscriptions
            subscriptions = await self.db_executor(
                """
                SELECT customer_id, plan_id, start_date, status
                FROM subscriptions
                WHERE status = 'active'
                """
            )
            
            # Generate statements
            for sub in subscriptions.get("rows", []):
                await self._generate_customer_statement(sub['customer_id'])
                
            return {"success": True, "count": len(subscriptions.get("rows", []))}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _generate_customer_statement(self, customer_id: str) -> Dict[str, Any]:
        """Generate statement for a single customer."""
        try:
            # Get customer's transactions
            transactions = await self.db_executor(
                f"""
                SELECT id, amount, currency, description, created_at
                FROM invoices
                WHERE customer_id = '{customer_id}'
                AND created_at >= NOW() - INTERVAL '1 month'
                ORDER BY created_at DESC
                """
            )
            
            # Calculate totals
            total_amount = sum(float(t['amount']) for t in transactions.get("rows", []))
            
            # Store statement
            await self.db_executor(
                f"""
                INSERT INTO billing_statements (
                    id, customer_id, period_start, period_end,
                    total_amount, currency, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    (NOW() - INTERVAL '1 month'),
                    NOW(),
                    {total_amount},
                    'USD',
                    NOW()
                )
                """
            )
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

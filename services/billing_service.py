"""
Billing Service - Handles subscriptions, invoices, and payments.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.database import query_db

class BillingService:
    def __init__(self):
        self.default_currency = "USD"
        self.tax_rate = 0.07  # Example tax rate

    async def create_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Create a new subscription for a customer."""
        try:
            # Get plan details
            plan_result = await query_db(f"""
                SELECT * FROM billing_plans WHERE id = '{plan_id}'
            """)
            plan = plan_result.get("rows", [{}])[0]
            
            if not plan:
                return {"error": "Plan not found"}

            # Calculate dates
            now = datetime.utcnow()
            billing_start = now
            billing_end = billing_start + timedelta(days=30)  # Monthly billing
            
            # Create subscription
            sub_result = await query_db(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    billing_start, billing_end, 
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan_id}',
                    'active',
                    '{billing_start.isoformat()}',
                    '{billing_end.isoformat()}',
                    NOW(),
                    NOW()
                ) RETURNING *
            """)
            
            subscription = sub_result.get("rows", [{}])[0]
            return {"subscription": subscription}
            
        except Exception as e:
            return {"error": str(e)}

    async def generate_invoice(self, subscription_id: str) -> Dict[str, Any]:
        """Generate an invoice for a subscription."""
        try:
            # Get subscription details
            sub_result = await query_db(f"""
                SELECT * FROM subscriptions WHERE id = '{subscription_id}'
            """)
            subscription = sub_result.get("rows", [{}])[0]
            
            if not subscription:
                return {"error": "Subscription not found"}

            # Get plan details
            plan_result = await query_db(f"""
                SELECT * FROM billing_plans WHERE id = '{subscription['plan_id']}'
            """)
            plan = plan_result.get("rows", [{}])[0]
            
            # Calculate amounts
            amount = float(plan.get("price", 0))
            tax = amount * self.tax_rate
            total = amount + tax
            
            # Create invoice
            invoice_result = await query_db(f"""
                INSERT INTO invoices (
                    id, subscription_id, amount, tax,
                    total, currency, status,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{subscription_id}',
                    {amount},
                    {tax},
                    {total},
                    '{self.default_currency}',
                    'pending',
                    NOW(),
                    NOW()
                ) RETURNING *
            """)
            
            invoice = invoice_result.get("rows", [{}])[0]
            return {"invoice": invoice}
            
        except Exception as e:
            return {"error": str(e)}

    async def process_payment(self, invoice_id: str, payment_method: str) -> Dict[str, Any]:
        """Process payment for an invoice."""
        try:
            # Get invoice details
            invoice_result = await query_db(f"""
                SELECT * FROM invoices WHERE id = '{invoice_id}'
            """)
            invoice = invoice_result.get("rows", [{}])[0]
            
            if not invoice:
                return {"error": "Invoice not found"}

            # Update invoice status
            await query_db(f"""
                UPDATE invoices
                SET status = 'paid',
                    payment_method = '{payment_method}',
                    paid_at = NOW(),
                    updated_at = NOW()
                WHERE id = '{invoice_id}'
            """)
            
            return {"success": True, "invoice_id": invoice_id}
            
        except Exception as e:
            return {"error": str(e)}

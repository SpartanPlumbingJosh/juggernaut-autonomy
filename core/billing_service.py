"""
SaaS Billing Service - Handles subscriptions, invoicing and payments.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class BillingService:
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql

    def create_subscription(self, customer_id: str, plan_id: str) -> Dict:
        """Create a new subscription for a customer."""
        try:
            # Get plan details
            plan = self.execute_sql(
                f"SELECT * FROM billing_plans WHERE id = '{plan_id}'"
            ).get("rows", [{}])[0]
            
            if not plan:
                return {"success": False, "error": "Plan not found"}
            
            # Create subscription
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=plan["billing_cycle_days"])
            
            result = self.execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    start_date, end_date, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan_id}',
                    'active',
                    '{start_date.isoformat()}',
                    '{end_date.isoformat()}',
                    NOW()
                )
                RETURNING id
                """
            )
            
            sub_id = result.get("rows", [{}])[0].get("id")
            if not sub_id:
                return {"success": False, "error": "Failed to create subscription"}
            
            # Create first invoice
            invoice = self.create_invoice(sub_id)
            
            return {
                "success": True,
                "subscription_id": sub_id,
                "invoice_id": invoice.get("invoice_id")
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_invoice(self, subscription_id: str) -> Dict:
        """Generate invoice for a subscription."""
        try:
            # Get subscription details
            sub = self.execute_sql(
                f"""
                SELECT s.*, p.amount_cents, p.currency, p.billing_cycle_days
                FROM subscriptions s
                JOIN billing_plans p ON s.plan_id = p.id
                WHERE s.id = '{subscription_id}'
                """
            ).get("rows", [{}])[0]
            
            if not sub:
                return {"success": False, "error": "Subscription not found"}
            
            # Create invoice
            due_date = datetime.utcnow() + timedelta(days=7)
            result = self.execute_sql(
                f"""
                INSERT INTO invoices (
                    id, subscription_id, amount_cents, currency,
                    status, due_date, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{subscription_id}',
                    {sub["amount_cents"]},
                    '{sub["currency"]}',
                    'pending',
                    '{due_date.isoformat()}',
                    NOW()
                )
                RETURNING id
                """
            )
            
            invoice_id = result.get("rows", [{}])[0].get("id")
            return {"success": True, "invoice_id": invoice_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_payment(self, invoice_id: str, payment_method: str) -> Dict:
        """Process payment for an invoice."""
        try:
            # Get invoice details
            invoice = self.execute_sql(
                f"SELECT * FROM invoices WHERE id = '{invoice_id}' AND status = 'pending'"
            ).get("rows", [{}])[0]
            
            if not invoice:
                return {"success": False, "error": "Invoice not found or already paid"}
            
            # Record payment
            self.execute_sql(
                f"""
                INSERT INTO payments (
                    id, invoice_id, amount_cents, currency,
                    payment_method, status, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{invoice_id}',
                    {invoice["amount_cents"]},
                    '{invoice["currency"]}',
                    '{payment_method}',
                    'completed',
                    NOW()
                )
                """
            )
            
            # Update invoice status
            self.execute_sql(
                f"UPDATE invoices SET status = 'paid', paid_at = NOW() WHERE id = '{invoice_id}'"
            )
            
            # Record revenue event
            self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {invoice["amount_cents"]},
                    '{invoice["currency"]}',
                    'subscription',
                    NOW(),
                    NOW()
                )
                """
            )
            
            # Renew subscription if needed
            sub = self.execute_sql(
                f"SELECT * FROM subscriptions WHERE id = '{invoice['subscription_id']}'"
            ).get("rows", [{}])[0]
            
            if sub and sub["status"] == "active" and datetime.utcnow() > datetime.fromisoformat(sub["end_date"]):
                new_end = datetime.fromisoformat(sub["end_date"]) + timedelta(days=30)
                self.execute_sql(
                    f"""
                    UPDATE subscriptions 
                    SET end_date = '{new_end.isoformat()}'
                    WHERE id = '{sub['id']}'
                    """
                )
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

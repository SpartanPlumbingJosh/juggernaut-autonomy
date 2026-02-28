from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid
import json

class BillingManager:
    """Handles invoicing, payments, subscriptions and revenue recognition."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    def create_invoice(self, customer_id: str, amount_cents: int, 
                      description: str, due_date: datetime) -> Dict[str, Any]:
        """Create a new invoice."""
        invoice_id = str(uuid.uuid4())
        sql = f"""
        INSERT INTO invoices (
            id, customer_id, amount_cents, description, 
            status, created_at, due_date, metadata
        ) VALUES (
            '{invoice_id}',
            '{customer_id}',
            {amount_cents},
            '{description.replace("'", "''")}',
            'pending',
            NOW(),
            '{due_date.isoformat()}',
            '{{}}'::jsonb
        )
        """
        self.execute_sql(sql)
        return {"invoice_id": invoice_id, "status": "created"}
        
    def record_payment(self, invoice_id: str, amount_cents: int,
                      payment_method: str, transaction_id: str) -> Dict[str, Any]:
        """Record a payment against an invoice."""
        payment_id = str(uuid.uuid4())
        sql = f"""
        INSERT INTO payments (
            id, invoice_id, amount_cents, payment_method,
            transaction_id, recorded_at, metadata
        ) VALUES (
            '{payment_id}',
            '{invoice_id}',
            {amount_cents},
            '{payment_method.replace("'", "''")}',
            '{transaction_id}',
            NOW(),
            '{{}}'::jsonb
        )
        """
        self.execute_sql(sql)
        
        # Update invoice status
        self.execute_sql(f"""
            UPDATE invoices
            SET status = CASE 
                WHEN amount_cents <= {amount_cents} THEN 'paid'
                ELSE 'partial'
            END
            WHERE id = '{invoice_id}'
        """)
        
        return {"payment_id": payment_id, "status": "recorded"}
        
    def create_subscription(self, customer_id: str, plan_id: str,
                          start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Create a new subscription."""
        sub_id = str(uuid.uuid4())
        sql = f"""
        INSERT INTO subscriptions (
            id, customer_id, plan_id, status,
            start_date, end_date, created_at, metadata
        ) VALUES (
            '{sub_id}',
            '{customer_id}',
            '{plan_id}',
            'active',
            '{start_date.isoformat()}',
            '{end_date.isoformat()}',
            NOW(),
            '{{}}'::jsonb
        )
        """
        self.execute_sql(sql)
        return {"subscription_id": sub_id, "status": "created"}
        
    def recognize_revenue(self, invoice_id: str, 
                        recognition_schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Record revenue recognition schedule."""
        recognition_id = str(uuid.uuid4())
        schedule_json = json.dumps(recognition_schedule).replace("'", "''")
        sql = f"""
        INSERT INTO revenue_recognition (
            id, invoice_id, schedule, status,
            created_at, metadata
        ) VALUES (
            '{recognition_id}',
            '{invoice_id}',
            '{schedule_json}'::jsonb,
            'pending',
            NOW(),
            '{{}}'::jsonb
        )
        """
        self.execute_sql(sql)
        return {"recognition_id": recognition_id, "status": "scheduled"}
        
    def process_recurring_payments(self) -> Dict[str, Any]:
        """Process recurring subscriptions and generate invoices."""
        # Get active subscriptions due for renewal
        sql = """
        SELECT s.id, s.customer_id, p.amount_cents, p.billing_cycle
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.status = 'active'
          AND s.end_date <= NOW() + INTERVAL '7 days'
        """
        result = self.execute_sql(sql)
        subscriptions = result.get("rows", [])
        
        processed = 0
        for sub in subscriptions:
            # Create new invoice
            invoice = self.create_invoice(
                customer_id=sub["customer_id"],
                amount_cents=sub["amount_cents"],
                description=f"Recurring subscription payment",
                due_date=datetime.utcnow() + timedelta(days=7)
            )
            
            # Extend subscription
            self.execute_sql(f"""
                UPDATE subscriptions
                SET end_date = end_date + INTERVAL '{sub["billing_cycle"]} days'
                WHERE id = '{sub["id"]}'
            """)
            
            processed += 1
            
        return {"processed": processed, "total": len(subscriptions)}

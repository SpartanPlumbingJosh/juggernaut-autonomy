from typing import Dict, List, Optional
from datetime import datetime, timedelta
from core.database import query_db, execute_db
from billing.payment_gateway import PaymentGateway

class InvoiceManager:
    def __init__(self, payment_gateway: PaymentGateway):
        self.payment_gateway = payment_gateway
        
    def generate_invoice(self, subscription_id: str) -> Dict:
        """Generate an invoice for a subscription"""
        # Get subscription details
        res = query_db(
            f"""
            SELECT s.*, p.amount, p.currency
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.id
            WHERE s.id = '{subscription_id}'
            """
        )
        subscription = res.get("rows", [{}])[0]
        
        if not subscription:
            return {"success": False, "error": "Subscription not found"}
            
        # Create invoice
        invoice_id = f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        execute_db(
            f"""
            INSERT INTO invoices (
                id, subscription_id, amount, currency,
                status, due_date, created_at, updated_at
            ) VALUES (
                '{invoice_id}',
                '{subscription_id}',
                {subscription['amount']},
                '{subscription['currency']}',
                'pending',
                NOW() + INTERVAL '7 days',
                NOW(),
                NOW()
            )
            """
        )
        
        return {
            "success": True,
            "invoice_id": invoice_id
        }
        
    def process_invoice(self, invoice_id: str) -> Dict:
        """Process payment for an invoice"""
        # Get invoice details
        res = query_db(
            f"""
            SELECT i.*, s.stripe_id
            FROM invoices i
            JOIN subscriptions s ON i.subscription_id = s.id
            WHERE i.id = '{invoice_id}'
            """
        )
        invoice = res.get("rows", [{}])[0]
        
        if not invoice:
            return {"success": False, "error": "Invoice not found"}
            
        # Process payment
        payment = self.payment_gateway.process_payment(
            amount=invoice['amount'],
            currency=invoice['currency'],
            payment_method_id=invoice['payment_method_id']
        )
        
        # Update invoice status
        execute_db(
            f"""
            UPDATE invoices
            SET status = 'paid',
                payment_id = '{payment['id']}',
                paid_at = NOW(),
                updated_at = NOW()
            WHERE id = '{invoice_id}'
            """
        )
        
        return {"success": True}
        
    def get_invoice(self, invoice_id: str) -> Optional[Dict]:
        """Get invoice details"""
        res = query_db(
            f"""
            SELECT *
            FROM invoices
            WHERE id = '{invoice_id}'
            """
        )
        return res.get("rows", [{}])[0]
        
    def list_invoices(self, customer_id: str, limit: int = 10, offset: int = 0) -> List[Dict]:
        """List invoices for a customer"""
        res = query_db(
            f"""
            SELECT i.*
            FROM invoices i
            JOIN subscriptions s ON i.subscription_id = s.id
            WHERE s.customer_id = '{customer_id}'
            ORDER BY i.created_at DESC
            LIMIT {limit}
            OFFSET {offset}
            """
        )
        return res.get("rows", [])

from datetime import datetime, timezone
from typing import Dict, Any
from core.database import execute_sql

class InvoiceManager:
    """Handle invoice generation and management."""
    
    async def generate_invoice(self, customer_id: str, amount: float, currency: str = "usd") -> Dict[str, Any]:
        """Generate an invoice for a customer."""
        try:
            invoice_number = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            
            await execute_sql(
                f"""
                INSERT INTO invoices (
                    id, customer_id, invoice_number, amount_cents, currency,
                    status, created_at, due_date
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{invoice_number}',
                    {int(amount * 100)},
                    '{currency}',
                    'pending',
                    NOW(),
                    NOW() + INTERVAL '30 days'
                )
                """
            )
            
            return {"success": True, "invoice_number": invoice_number}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def mark_invoice_paid(self, invoice_id: str) -> Dict[str, Any]:
        """Mark an invoice as paid."""
        try:
            await execute_sql(
                f"""
                UPDATE invoices
                SET status = 'paid',
                    paid_at = NOW()
                WHERE id = '{invoice_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

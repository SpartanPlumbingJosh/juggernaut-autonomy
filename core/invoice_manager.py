from __future__ import annotations
from datetime import datetime
from typing import Dict, Optional, Any
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class InvoiceManager:
    """Handle invoice generation and management."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def generate_invoice(self, subscription_id: str, amount: Decimal, currency: str = "USD") -> Dict[str, Any]:
        """Generate a new invoice for a subscription."""
        try:
            sql = f"""
            INSERT INTO invoices (
                id, subscription_id, amount, currency,
                status, created_at, due_date
            ) VALUES (
                gen_random_uuid(),
                '{subscription_id}',
                {float(amount)},
                '{currency}',
                'pending',
                NOW(),
                NOW() + INTERVAL '30 days'
            )
            RETURNING id
            """
            result = await self.execute_sql(sql)
            invoice_id = result.get("rows", [{}])[0].get("id")
            
            if invoice_id:
                return {"success": True, "invoice_id": invoice_id}
            return {"success": False, "error": "Failed to generate invoice"}
        except Exception as e:
            logger.error(f"Invoice generation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def process_paid_invoices(self) -> Dict[str, Any]:
        """Process paid invoices and update accounting records."""
        try:
            # Get paid invoices
            sql = """
            SELECT id, subscription_id, amount, currency
            FROM invoices
            WHERE status = 'paid'
              AND processed_at IS NULL
            LIMIT 100
            """
            result = await self.execute_sql(sql)
            invoices = result.get("rows", [])
            
            processed = 0
            failures = []
            
            for invoice in invoices:
                process_result = await self._process_invoice(invoice)
                if process_result.get("success"):
                    processed += 1
                else:
                    failures.append({
                        "invoice_id": invoice.get("id"),
                        "error": process_result.get("error")
                    })
                    
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
        except Exception as e:
            logger.error(f"Invoice processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _process_invoice(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Process an individual invoice."""
        try:
            # Update invoice status
            sql = f"""
            UPDATE invoices
            SET processed_at = NOW()
            WHERE id = '{invoice.get("id")}'
            """
            await self.execute_sql(sql)
            
            # Create revenue event
            revenue_sql = f"""
            INSERT INTO revenue_events (
                id, subscription_id, event_type,
                amount_cents, currency, source,
                recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                '{invoice.get("subscription_id")}',
                'revenue',
                {int(float(invoice.get("amount")) * 100)},
                '{invoice.get("currency")}',
                'subscription',
                NOW(),
                NOW()
            )
            """
            await self.execute_sql(revenue_sql)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

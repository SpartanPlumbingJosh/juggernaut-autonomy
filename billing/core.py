"""
Core billing infrastructure - handles subscriptions, metering, and invoicing.
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal

from core.database import query_db

class BillingEngine:
    """Handles all automated billing operations."""
    
    def __init__(self, payment_processor: str = "stripe"):
        self.processor = payment_processor.lower()
        
    async def create_subscription(self, customer_id: str, plan_id: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a new subscription."""
        metadata = metadata or {}
        
        # Store in database
        sub_id = await query_db(
            f"""
            INSERT INTO subscriptions (
                customer_id, plan_id, status, 
                current_period_start, current_period_end,
                metadata, created_at
            ) VALUES (
                '{customer_id}', '{plan_id}', 'active',
                NOW(), NOW() + INTERVAL '1 month',
                '{json.dumps(metadata)}'::jsonb, NOW()
            )
            RETURNING id
            """
        )
        
        # Process payment
        payment_result = await self._charge_subscription(sub_id, plan_id)
        
        return {
            "subscription_id": sub_id,
            "payment_status": payment_result["status"],
            "invoice_id": payment_result.get("invoice_id")
        }
    
    async def record_usage(self, customer_id: str, metric: str, units: int) -> Dict[str, Any]:
        """Record usage for metered billing."""
        await query_db(
            f"""
            INSERT INTO usage_records (
                customer_id, metric, units, 
                recorded_at
            ) VALUES (
                '{customer_id}', '{metric}', {units},
                NOW()
            )
            """
        )
        return {"success": True}
    
    async def generate_invoice(self, customer_id: str) -> Dict[str, Any]:
        """Generate invoice for customer."""
        # Get all unbilled usage
        usage = await query_db(
            f"""
            SELECT metric, SUM(units) as total_units
            FROM usage_records
            WHERE customer_id = '{customer_id}'
              AND billed = FALSE
            GROUP BY metric
            """
        )
        
        # Calculate totals
        invoice_lines = []
        total_amount = Decimal('0')
        
        for row in usage.get("rows", []):
            metric = row["metric"]
            units = Decimal(str(row["total_units"]))
            rate = await self._get_rate(metric)
            amount = units * rate
            
            invoice_lines.append({
                "metric": metric,
                "units": units,
                "rate": rate,
                "amount": amount
            })
            total_amount += amount
        
        # Create invoice
        invoice_id = await query_db(
            f"""
            INSERT INTO invoices (
                customer_id, amount, currency,
                status, due_date, metadata,
                created_at
            ) VALUES (
                '{customer_id}', {total_amount}, 'USD',
                'pending', NOW() + INTERVAL '30 days',
                '{json.dumps({"lines": invoice_lines})}'::jsonb,
                NOW()
            )
            RETURNING id
            """
        )
        
        # Mark usage as billed
        await query_db(
            f"""
            UPDATE usage_records
            SET billed = TRUE,
                invoice_id = '{invoice_id}'
            WHERE customer_id = '{customer_id}'
              AND billed = FALSE
            """
        )
        
        return {
            "invoice_id": invoice_id,
            "amount": total_amount,
            "lines": invoice_lines
        }
    
    async def process_payment(self, invoice_id: str) -> Dict[str, Any]:
        """Process payment for an invoice."""
        invoice = await query_db(
            f"""
            SELECT customer_id, amount, currency
            FROM invoices
            WHERE id = '{invoice_id}'
            """
        )
        
        if not invoice.get("rows"):
            return {"success": False, "error": "Invoice not found"}
        
        customer_id = invoice["rows"][0]["customer_id"]
        amount = invoice["rows"][0]["amount"]
        
        # Process payment
        payment_result = await self._charge_customer(customer_id, amount)
        
        if payment_result["success"]:
            await query_db(
                f"""
                UPDATE invoices
                SET status = 'paid',
                    paid_at = NOW(),
                    payment_method = '{self.processor}',
                    payment_reference = '{payment_result["payment_id"]}'
                WHERE id = '{invoice_id}'
                """
            )
            
            # Record revenue event
            await self._record_revenue_event(
                customer_id=customer_id,
                amount=amount,
                source="subscription",
                invoice_id=invoice_id
            )
            
            return {"success": True, "payment_id": payment_result["payment_id"]}
        
        return {"success": False, "error": payment_result.get("error")}
    
    async def _charge_subscription(self, subscription_id: str, plan_id: str) -> Dict[str, Any]:
        """Charge subscription payment."""
        # Implement processor-specific logic
        return {"status": "succeeded", "invoice_id": "inv_123"}
    
    async def _charge_customer(self, customer_id: str, amount: Decimal) -> Dict[str, Any]:
        """Charge customer payment."""
        # Implement processor-specific logic
        return {"success": True, "payment_id": "pmt_123"}
    
    async def _get_rate(self, metric: str) -> Decimal:
        """Get rate for usage metric."""
        rates = {
            "api_calls": Decimal('0.001'),
            "storage_gb": Decimal('0.10'),
            "users": Decimal('5.00')
        }
        return rates.get(metric, Decimal('0'))
    
    async def _record_revenue_event(
        self,
        customer_id: str,
        amount: Decimal,
        source: str,
        invoice_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Record revenue event in accounting system."""
        metadata = metadata or {}
        if invoice_id:
            metadata["invoice_id"] = invoice_id
            
        await query_db(
            f"""
            INSERT INTO revenue_events (
                event_type, amount_cents, currency,
                source, metadata, recorded_at
            ) VALUES (
                'revenue', {int(amount * 100)}, 'USD',
                '{source}', '{json.dumps(metadata)}'::jsonb,
                NOW()
            )
            """
        )
        return {"success": True}

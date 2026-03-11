from datetime import datetime, timedelta
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from core.database import query_db

logger = logging.getLogger(__name__)

class BillingManager:
    """Handles automated billing, payment processing, and service delivery."""
    
    def __init__(self):
        self.retry_attempts = 3
        self.retry_delay = 60  # seconds
        
    async def process_pending_invoices(self, execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
        """Process all pending invoices."""
        try:
            # Get pending invoices
            res = await execute_sql(
                """
                SELECT id, customer_id, amount_cents, currency, due_date, metadata
                FROM invoices
                WHERE status = 'pending'
                  AND due_date <= NOW()
                ORDER BY due_date ASC
                LIMIT 100
                """
            )
            invoices = res.get("rows", []) or []
            
            processed = 0
            failures = []
            
            for invoice in invoices:
                invoice_id = str(invoice.get("id") or "")
                if not invoice_id:
                    continue
                    
                # Attempt payment processing with retries
                success = False
                last_error = None
                
                for attempt in range(self.retry_attempts):
                    try:
                        payment_result = await self._process_payment(invoice)
                        if payment_result.get("success"):
                            success = True
                            break
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(f"Payment attempt {attempt+1} failed for invoice {invoice_id}: {last_error}")
                        await asyncio.sleep(self.retry_delay)
                        
                if success:
                    # Mark invoice as paid
                    await execute_sql(
                        f"""
                        UPDATE invoices
                        SET status = 'paid',
                            paid_at = NOW(),
                            updated_at = NOW()
                        WHERE id = '{invoice_id}'
                        """
                    )
                    processed += 1
                    
                    # Trigger service delivery
                    await self._deliver_service(invoice)
                else:
                    failures.append({
                        "invoice_id": invoice_id,
                        "error": last_error or "Payment failed after retries"
                    })
                    
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
            
        except Exception as e:
            logger.error(f"Failed to process invoices: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def _process_payment(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment for an invoice."""
        # Implement actual payment gateway integration here
        # For now, simulate successful payment
        return {"success": True}
        
    async def _deliver_service(self, invoice: Dict[str, Any]) -> None:
        """Deliver service/product after successful payment."""
        # Implement service delivery logic here
        pass
        
    async def generate_recurring_invoices(self, execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
        """Generate recurring invoices based on subscriptions."""
        try:
            # Get active subscriptions due for renewal
            res = await execute_sql(
                """
                SELECT id, customer_id, plan_id, billing_cycle, next_billing_date
                FROM subscriptions
                WHERE status = 'active'
                  AND next_billing_date <= NOW()
                ORDER BY next_billing_date ASC
                LIMIT 100
                """
            )
            subscriptions = res.get("rows", []) or []
            
            generated = 0
            failures = []
            
            for sub in subscriptions:
                subscription_id = str(sub.get("id") or "")
                if not subscription_id:
                    continue
                    
                try:
                    # Create new invoice
                    invoice_data = await self._create_invoice_for_subscription(sub)
                    await execute_sql(
                        f"""
                        INSERT INTO invoices (
                            id, customer_id, subscription_id, amount_cents, currency,
                            due_date, status, created_at, updated_at, metadata
                        ) VALUES (
                            gen_random_uuid(),
                            '{invoice_data["customer_id"]}',
                            '{subscription_id}',
                            {invoice_data["amount_cents"]},
                            '{invoice_data["currency"]}',
                            '{invoice_data["due_date"]}',
                            'pending',
                            NOW(),
                            NOW(),
                            '{json.dumps(invoice_data["metadata"])}'::jsonb
                        )
                        """
                    )
                    
                    # Update subscription next billing date
                    await execute_sql(
                        f"""
                        UPDATE subscriptions
                        SET next_billing_date = '{invoice_data["next_billing_date"]}',
                            updated_at = NOW()
                        WHERE id = '{subscription_id}'
                        """
                    )
                    
                    generated += 1
                except Exception as e:
                    failures.append({
                        "subscription_id": subscription_id,
                        "error": str(e)
                    })
                    
            return {
                "success": True,
                "generated": generated,
                "failures": failures
            }
            
        except Exception as e:
            logger.error(f"Failed to generate recurring invoices: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def _create_invoice_for_subscription(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Create invoice data for a subscription."""
        # Implement actual invoice generation logic here
        # For now, return mock data
        return {
            "customer_id": subscription["customer_id"],
            "amount_cents": 1000,  # $10.00
            "currency": "USD",
            "due_date": datetime.utcnow().isoformat(),
            "next_billing_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "metadata": {
                "plan_id": subscription["plan_id"],
                "billing_cycle": subscription["billing_cycle"]
            }
        }

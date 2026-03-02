from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from core.database import query_db, execute_db
from billing.payment_processor import PaymentProcessor

class BillingManager:
    def __init__(self, payment_processor: PaymentProcessor):
        self.payment_processor = payment_processor
        
    async def create_invoice(self, customer_id: str, amount_cents: int, currency: str = 'usd') -> Dict[str, Any]:
        """Create and send an invoice."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method='send_invoice',
                days_until_due=30,
                currency=currency,
                metadata={}
            )
            
            invoice_item = stripe.InvoiceItem.create(
                customer=customer_id,
                amount=amount_cents,
                currency=currency,
                invoice=invoice.id
            )
            
            final_invoice = stripe.Invoice.finalize_invoice(invoice.id)
            stripe.Invoice.send_invoice(invoice.id)
            
            return {"success": True, "invoice": final_invoice}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def process_recurring_billing(self) -> Dict[str, Any]:
        """Process all recurring subscriptions."""
        try:
            # Get active subscriptions due for renewal
            res = await query_db(
                """
                SELECT id, customer_id, price_id, status, next_billing_date
                FROM subscriptions
                WHERE status = 'active'
                  AND next_billing_date <= NOW()
                """
            )
            subscriptions = res.get("rows", [])
            
            processed = 0
            failures = []
            
            for sub in subscriptions:
                result = await self.payment_processor.create_subscription(
                    sub['customer_id'],
                    sub['price_id']
                )
                
                if result['success']:
                    processed += 1
                    # Update next billing date
                    await execute_db(
                        f"""
                        UPDATE subscriptions
                        SET next_billing_date = NOW() + INTERVAL '1 month',
                            last_billed_at = NOW()
                        WHERE id = '{sub['id']}'
                        """
                    )
                else:
                    failures.append({
                        "subscription_id": sub['id'],
                        "error": result.get('error', 'Unknown error')
                    })
                    
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

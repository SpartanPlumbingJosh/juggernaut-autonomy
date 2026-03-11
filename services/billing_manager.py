"""
Billing Manager - Handles subscription billing and invoicing.
"""

from datetime import datetime, timedelta
from typing import Dict, Any
from core.database import query_db
from services.payment_processor import PaymentProcessor

class BillingManager:
    def __init__(self, payment_processor: PaymentProcessor):
        self.payment_processor = payment_processor

    async def process_subscription_payments(self) -> Dict[str, Any]:
        """Process recurring subscription payments."""
        try:
            # Get active subscriptions due for payment
            subscriptions = await query_db("""
                SELECT c.id, c.customer_id, p.amount_cents, p.currency
                FROM customers c
                JOIN plans p ON c.plan = p.name
                WHERE c.status = 'active'
                  AND c.next_payment_due <= NOW()
            """)
            
            processed = 0
            failures = []
            
            for sub in subscriptions.get('rows', []):
                payment_result = await self.payment_processor.process_payment(
                    amount_cents=sub['amount_cents'],
                    currency=sub['currency'],
                    customer_id=sub['customer_id'],
                    description="Recurring subscription payment"
                )
                
                if payment_result['success']:
                    await query_db(f"""
                        UPDATE customers
                        SET last_payment_at = NOW(),
                            next_payment_due = NOW() + INTERVAL '1 month'
                        WHERE id = '{sub['id']}'
                    """)
                    processed += 1
                else:
                    failures.append({
                        'customer_id': sub['customer_id'],
                        'error': payment_result.get('error', 'Unknown error')
                    })
            
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def generate_invoices(self) -> Dict[str, Any]:
        """Generate invoices for completed payments."""
        try:
            # Get payments without invoices
            payments = await query_db("""
                SELECT id, amount_cents, currency, customer_id, recorded_at
                FROM revenue_events
                WHERE event_type = 'payment'
                  AND invoice_id IS NULL
            """)
            
            generated = 0
            
            for payment in payments.get('rows', []):
                invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{payment['id'][:8]}"
                
                await query_db(f"""
                    INSERT INTO invoices (
                        id, invoice_number, amount_cents, currency,
                        customer_id, payment_id, issued_at
                    ) VALUES (
                        gen_random_uuid(),
                        '{invoice_number}',
                        {payment['amount_cents']},
                        '{payment['currency']}',
                        '{payment['customer_id']}',
                        '{payment['id']}',
                        NOW()
                    )
                """)
                
                await query_db(f"""
                    UPDATE revenue_events
                    SET invoice_id = (
                        SELECT id FROM invoices 
                        WHERE payment_id = '{payment['id']}'
                        LIMIT 1
                    )
                    WHERE id = '{payment['id']}'
                """)
                
                generated += 1
                
            return {"success": True, "generated": generated}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

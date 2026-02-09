import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db, execute_db

logger = logging.getLogger(__name__)

class AutomatedBillingSystem:
    """Handles automated billing and payment processing."""
    
    def __init__(self):
        self.payment_processors = {
            'stripe': self._process_stripe_payment,
            'paypal': self._process_paypal_payment
        }
    
    async def process_payment(self, customer_id: str, amount: float, currency: str = 'USD') -> Dict[str, Any]:
        """Process a payment for a customer."""
        try:
            # Get customer payment method
            res = await query_db(f"""
                SELECT payment_method, payment_processor
                FROM customers
                WHERE id = '{customer_id}'
            """)
            customer = res.get("rows", [{}])[0]
            
            processor = customer.get("payment_processor", "stripe")
            processor_fn = self.payment_processors.get(processor)
            
            if not processor_fn:
                return {"success": False, "error": f"Unknown payment processor: {processor}"}
            
            # Process payment
            result = await processor_fn(
                customer_id=customer_id,
                payment_method=customer.get("payment_method"),
                amount=amount,
                currency=currency
            )
            
            if not result.get("success"):
                return result
                
            # Record transaction
            await execute_db(f"""
                INSERT INTO revenue_events (
                    id, customer_id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    'revenue',
                    {int(amount * 100)},
                    '{currency}',
                    'automated_billing',
                    '{{"processor": "{processor}"}}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
            return {"success": True, "transaction_id": result.get("transaction_id")}
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _process_stripe_payment(self, customer_id: str, payment_method: str, amount: float, currency: str) -> Dict[str, Any]:
        """Process payment via Stripe."""
        # Implementation would call Stripe API
        return {"success": True, "transaction_id": "stripe_txn_123"}
    
    async def _process_paypal_payment(self, customer_id: str, payment_method: str, amount: float, currency: str) -> Dict[str, Any]:
        """Process payment via PayPal."""
        # Implementation would call PayPal API
        return {"success": True, "transaction_id": "paypal_txn_123"}
    
    async def generate_invoices(self) -> Dict[str, Any]:
        """Generate invoices for all active subscriptions."""
        try:
            # Get active subscriptions
            res = await query_db("""
                SELECT s.id, s.customer_id, s.plan_id, s.billing_cycle, s.next_billing_date,
                       p.price_cents, p.currency
                FROM subscriptions s
                JOIN plans p ON s.plan_id = p.id
                WHERE s.status = 'active'
                  AND s.next_billing_date <= NOW()
            """)
            subscriptions = res.get("rows", [])
            
            processed = 0
            failures = []
            
            for sub in subscriptions:
                try:
                    # Process payment
                    amount = float(sub.get("price_cents", 0)) / 100
                    result = await self.process_payment(
                        customer_id=sub.get("customer_id"),
                        amount=amount,
                        currency=sub.get("currency", "USD")
                    )
                    
                    if not result.get("success"):
                        failures.append({
                            "subscription_id": sub.get("id"),
                            "error": result.get("error")
                        })
                        continue
                        
                    # Update subscription
                    await execute_db(f"""
                        UPDATE subscriptions
                        SET last_payment_date = NOW(),
                            next_billing_date = NOW() + INTERVAL '1 {sub.get("billing_cycle")}',
                            updated_at = NOW()
                        WHERE id = '{sub.get("id")}'
                    """)
                    
                    processed += 1
                    
                except Exception as e:
                    failures.append({
                        "subscription_id": sub.get("id"),
                        "error": str(e)
                    })
                    continue
                    
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
            
        except Exception as e:
            logger.error(f"Invoice generation failed: {str(e)}")
            return {"success": False, "error": str(e)}

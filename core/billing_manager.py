from datetime import datetime, timedelta
from typing import Dict, List
from core.database import execute_sql
from core.payment_processor import PaymentProcessor
import os

class BillingManager:
    def __init__(self):
        self.processor = PaymentProcessor(api_key=os.getenv("STRIPE_SECRET_KEY"))

    async def process_subscriptions(self) -> Dict:
        """Process all active subscriptions."""
        try:
            # Get subscriptions due for payment
            res = await execute_sql(
                """
                SELECT id, customer_id, plan_id, amount_cents, currency, next_billing_at
                FROM subscriptions
                WHERE status = 'active'
                  AND next_billing_at <= NOW()
                LIMIT 100
                """
            )
            subscriptions = res.get("rows", [])
            
            processed = 0
            failures = []
            
            for sub in subscriptions:
                try:
                    # Create payment intent
                    result = await self.processor.create_payment_intent(
                        sub["amount_cents"],
                        sub["currency"],
                        sub["customer_id"]
                    )
                    
                    if not result.get("success"):
                        failures.append({
                            "subscription_id": sub["id"],
                            "error": result.get("error")
                        })
                        continue
                        
                    # Update subscription
                    await execute_sql(
                        f"""
                        UPDATE subscriptions
                        SET last_billed_at = NOW(),
                            next_billing_at = NOW() + INTERVAL '1 month',
                            updated_at = NOW()
                        WHERE id = '{sub["id"]}'
                        """
                    )
                    processed += 1
                    
                except Exception as e:
                    failures.append({
                        "subscription_id": sub["id"],
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_failed_payments(self) -> Dict:
        """Handle failed subscription payments."""
        try:
            # Get failed payments
            res = await execute_sql(
                """
                SELECT id, customer_id, subscription_id, amount_cents, currency
                FROM payment_attempts
                WHERE status = 'failed'
                  AND retry_count < 3
                LIMIT 100
                """
            )
            attempts = res.get("rows", [])
            
            retried = 0
            failures = []
            
            for attempt in attempts:
                try:
                    # Retry payment
                    result = await self.processor.create_payment_intent(
                        attempt["amount_cents"],
                        attempt["currency"],
                        attempt["customer_id"]
                    )
                    
                    if not result.get("success"):
                        failures.append({
                            "attempt_id": attempt["id"],
                            "error": result.get("error")
                        })
                        continue
                        
                    # Update attempt record
                    await execute_sql(
                        f"""
                        UPDATE payment_attempts
                        SET retry_count = retry_count + 1,
                            last_attempt_at = NOW(),
                            status = 'retried',
                            updated_at = NOW()
                        WHERE id = '{attempt["id"]}'
                        """
                    )
                    retried += 1
                    
                except Exception as e:
                    failures.append({
                        "attempt_id": attempt["id"],
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "retried": retried,
                "failures": failures
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

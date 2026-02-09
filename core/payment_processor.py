"""Core payment processing and revenue generation system."""
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

class PaymentProcessor:
    def __init__(self, db_executor, logger):
        self.db = db_executor
        self.log = logger
    
    async def process_payment(self, amount: float, currency: str, 
                            customer_id: str, service_id: str,
                            description: str = "") -> Dict[str, Any]:
        """Process a payment and record the revenue."""
        try:
            # Record revenue event
            amount_cents = int(amount * 100)
            revenue_id = await self._record_revenue(
                amount_cents=amount_cents,
                currency=currency,
                customer_id=customer_id,
                service_id=service_id,
                description=description
            )
            
            return {
                "success": True,
                "revenue_id": revenue_id,
                "amount_cents": amount_cents
            }
            
        except Exception as e:
            self.log(
                "payment.failed", 
                f"Payment processing failed: {str(e)}",
                level="error",
                error_data={"error": str(e), "service_id": service_id}
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _record_revenue(self, amount_cents: int, currency: str,
                            customer_id: str, service_id: str,
                            description: str) -> str:
        """Record revenue transaction in database."""
        result = await self.db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                customer_id, service_id, description,
                recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{currency}',
                '{customer_id.replace("'", "''")}',
                '{service_id.replace("'", "''")}',
                '{description.replace("'", "''")}',
                NOW(),
                NOW()
            )
            RETURNING id
            """
        )
        return result["rows"][0]["id"]
    
    async def issue_refund(self, original_revenue_id: str, 
                         amount_cents: Optional[int] = None) -> Dict[str, Any]:
        """Process a refund and record negative revenue."""
        try:
            # Get original transaction
            original_result = await self.db(
                f"""
                SELECT amount_cents, currency, customer_id, service_id
                FROM revenue_events 
                WHERE id = '{original_revenue_id.replace("'", "''")}'
                """
            )
            original = original_result["rows"][0]
            
            amount = - (amount_cents or original["amount_cents"])
            refund_id = await self._record_revenue(
                amount_cents=amount,
                currency=original["currency"],
                customer_id=original["customer_id"],
                service_id=original["service_id"],
                description="Refund"
            )
            
            return {
                "success": True,
                "refund_id": refund_id 
            }
            
        except Exception as e:
            self.log(
                "refund.failed",
                f"Refund processing failed: {str(e)}",
                level="error",
                error_data={"original_revenue_id": original_revenue_id}
            )
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_recurring_billing(self) -> Dict[str, Any]:
        """Process all pending recurring billing."""
        try:
            # Get active subscriptions
            result = await self.db(
                """
                SELECT s.id, s.customer_id, s.service_id, s.recurring_amount_cents,
                       s.currency, s.billing_cycle_days, s.last_billed_at,
                       p.payment_method_token
                FROM subscriptions s
                JOIN payment_methods p ON s.customer_id = p.customer_id AND p.is_default=true
                WHERE s.is_active = true
                AND (s.last_billed_at IS NULL OR 
                     s.last_billed_at + (s.billing_cycle_days || ' days')::INTERVAL <= NOW())
                """
            )
            
            processed = 0
            failures = 0
            
            for sub in result["rows"]:
                billing_result = await self.process_payment(
                    amount=sub["recurring_amount_cents"] / 100,
                    currency=sub["currency"],
                    customer_id=sub["customer_id"],
                    service_id=sub["service_id"],
                    description=f"Recurring subscription payment"
                )
                
                if billing_result["success"]:
                    # Update subscription billing date
                    await self.db(
                        f"""
                        UPDATE subscriptions
                        SET last_billed_at = NOW(),
                            updated_at = NOW()
                        WHERE id = '{sub["id"]}'
                        """
                    )
                    processed += 1
                else:
                    failures += 1
            
            self.log(
                "billing.recurring_processed",
                f"Processed {processed} recurring payments ({failures} failures)",
                level="info"
            )
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
            
        except Exception as e:
            self.log(
                "billing.recurring_failed",
                f"Recurring billing failed: {str(e)}",
                level="error"
            )
            return {
                "success": False,
                "error": str(e)
            }

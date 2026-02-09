"""
Payment Processor - Handles payment integrations and transaction processing.
Supports Stripe for credit card payments and PayPal for alternative payments.
"""

import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional

class PaymentProcessor:
    def __init__(self, stripe_api_key: str, paypal_config: Dict[str, str]):
        stripe.api_key = stripe_api_key
        paypalrestsdk.configure({
            "mode": paypal_config.get("mode", "sandbox"),
            "client_id": paypal_config["client_id"],
            "client_secret": paypal_config["client_secret"]
        })

    async def create_payment_intent(self, amount: float, currency: str, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                metadata=metadata
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_id": intent.id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_paypal_payment(self, amount: float, currency: str, return_url: str, cancel_url: str) -> Dict[str, Any]:
        """Create a PayPal payment."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency
                    }
                }],
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url
                }
            })
            
            if payment.create():
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "approval_url": next(link.href for link in payment.links if link.method == "REDIRECT")
                }
            return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_transaction(self, payment_id: str, amount: float, currency: str, 
                               payment_method: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Record a completed transaction."""
        try:
            # Record in revenue_events table
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount * 100)},
                '{currency}',
                '{payment_method}',
                '{{"payment_id": "{payment_id}", "user_id": "{user_id or ''}"}}'::jsonb,
                NOW(),
                NOW()
            )
            """
            # Execute SQL (assuming execute_sql is available)
            await query_db(sql)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

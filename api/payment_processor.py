"""
Payment Processor - Handles Stripe and PayPal integrations for revenue generation.
"""

import os
import stripe
import paypalrestsdk
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Initialize payment processors
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET')
})

class PaymentProcessor:
    @staticmethod
    async def create_stripe_payment(amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={"enabled": True}
            )
            return {
                "client_secret": intent.client_secret,
                "payment_id": intent.id,
                "status": "requires_payment_method"
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def create_paypal_order(amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PayPal order."""
        try:
            order = paypalrestsdk.Order({
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": str(amount)
                    },
                    "custom_id": metadata.get("experiment_id", ""),
                    "description": metadata.get("description", "")
                }]
            })
            
            if order.create():
                return {
                    "order_id": order.id,
                    "approval_url": next(link.href for link in order.links if link.rel == "approve"),
                    "status": order.status
                }
            return {"error": order.error}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def record_payment_event(
        execute_sql: callable,
        payment_data: Dict[str, Any],
        event_type: str = "revenue"
    ) -> bool:
        """Record payment event in revenue_events table."""
        try:
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {int(float(payment_data.get('amount', 0)) * 100)},
                    '{payment_data.get('currency', 'usd')}',
                    '{payment_data.get('source', 'stripe')}',
                    '{json.dumps(payment_data.get('metadata', {}))}',
                    NOW(),
                    NOW()
                )
                """
            )
            return True
        except Exception:
            return False

__all__ = ["PaymentProcessor"]

"""Payment processing service with Stripe/Paypal integration."""
import os
from datetime import datetime, timezone
from typing import Dict, Optional, Union

import stripe
import paypalrestsdk
from core.database import query_db

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_SECRET")
})

class PaymentService:
    @staticmethod
    async def create_payment_intent(amount_cents: int, currency: str, metadata: Dict) -> Dict:
        """Create Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                receipt_email=metadata.get('customer_email'),
                setup_future_usage='off_session' if metadata.get('subscription') else None
            )
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_id": intent.id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def create_paypal_payment(amount_cents: int, currency: str, metadata: Dict) -> Dict:
        """Create PayPal payment."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount_cents / 100:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get('description')
                }],
                "redirect_urls": {
                    "return_url": metadata.get('success_url'),
                    "cancel_url": metadata.get('cancel_url')
                }
            })
            if payment.create():
                return {
                    "success": True,
                    "approval_url": next(
                        link.href for link in payment.links if link.method == "REDIRECT"
                    ),
                    "payment_id": payment.id
                }
            return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def record_transaction(
        payment_id: str,
        amount_cents: int,
        currency: str,
        status: str,
        source: str,
        metadata: Dict
    ) -> bool:
        """Record transaction in database."""
        try:
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, status, metadata, recorded_at
                ) VALUES (
                    '{payment_id}', 'revenue', {amount_cents}, '{currency}',
                    '{source}', '{status}', '{json.dumps(metadata)}', NOW()
                )
                """
            )
            return True
        except Exception:
            return False

    @staticmethod
    async def handle_webhook(event_data: Dict, source: str) -> bool:
        """Process payment webhook events."""
        if source == "stripe":
            event = stripe.Event.construct_from(event_data, stripe.api_key)
            if event.type == "payment_intent.succeeded":
                payment_intent = event.data.object
                return await PaymentService.record_transaction(
                    payment_intent.id,
                    payment_intent.amount,
                    payment_intent.currency,
                    "completed",
                    "stripe",
                    payment_intent.metadata
                )
        elif source == "paypal":
            # PayPal webhook handling logic
            pass
        return False



async def create_subscription(
    customer_id: str,
    plan_id: str,
    payment_method: str,
    metadata: Optional[Dict] = None
) -> Dict[str, Union[bool, str]]:
    """Create recurring subscription."""
    try:
        sub = stripe.Subscription.create(
            customer=customer_id,
            items=[{"plan": plan_id}],
            default_payment_method=payment_method,
            metadata=metadata or {}
        )
        return {"success": True, "subscription_id": sub.id}
    except stripe.error.StripeError as e:
        return {"success": False, "error": str(e)}

import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Any, Optional

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })

    async def create_stripe_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_paypal_order(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PayPal order."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency
                    },
                    "description": metadata.get("description", "")
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if payment.create():
                return {"success": True, "approval_url": payment.links[1].href}
            return {"success": False, "error": "Failed to create PayPal payment"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_stripe_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return await self._record_payment(
                    provider='stripe',
                    payment_id=payment_intent['id'],
                    amount=payment_intent['amount'],
                    currency=payment_intent['currency'],
                    metadata=payment_intent.get('metadata', {})
                )
                
            return {"success": True, "event": event['type']}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_paypal_webhook(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal webhook events."""
        try:
            if event['event_type'] == 'PAYMENT.SALE.COMPLETED':
                resource = event['resource']
                return await self._record_payment(
                    provider='paypal',
                    payment_id=resource['id'],
                    amount=float(resource['amount']['total']) * 100,
                    currency=resource['amount']['currency'],
                    metadata={}
                )
                
            return {"success": True, "event": event['event_type']}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _record_payment(self, provider: str, payment_id: str, amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Record payment in revenue ledger."""
        from core.database import query_db
        
        try:
            await query_db(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount},
                    '{currency}',
                    '{provider}',
                    '{json.dumps(metadata)}',
                    NOW(),
                    NOW()
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

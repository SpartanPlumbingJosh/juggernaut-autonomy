import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from core.database import query_db, execute_sql

class PaymentProcessor:
    def __init__(self):
        # Initialize payment gateways
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })
        
    async def process_payment(self, payment_method: str, amount: float, currency: str, 
                            customer_email: str, metadata: Dict) -> Tuple[bool, Optional[str], Optional[str]]:
        """Process payment through selected gateway."""
        try:
            amount_cents = int(amount * 100)
            
            if payment_method == 'stripe':
                payment = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency,
                    receipt_email=customer_email,
                    metadata=metadata
                )
                if payment.status == 'succeeded':
                    return True, payment.id, None
                
            elif payment_method == 'paypal':
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount:.2f}",
                            "currency": currency
                        },
                        "description": metadata.get('description', '')
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv('PAYPAL_RETURN_URL'),
                        "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                    }
                })
                if payment.create():
                    return True, payment.id, None
                    
            return False, None, "Payment failed"
            
        except Exception as e:
            return False, None, str(e)
            
    async def record_transaction(self, payment_id: str, amount: float, currency: str, 
                               event_type: str, source: str, metadata: Dict) -> bool:
        """Record transaction in revenue_events table."""
        try:
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {int(amount * 100)},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}',
                    NOW(),
                    NOW()
                )
                """
            )
            return True
        except Exception:
            return False
            
    async def handle_webhook(self, gateway: str, payload: Dict) -> Dict:
        """Process payment gateway webhooks."""
        try:
            if gateway == 'stripe':
                event = stripe.Webhook.construct_event(
                    payload,
                    os.getenv('STRIPE_WEBHOOK_SECRET'),
                    os.getenv('STRIPE_WEBHOOK_TOLERANCE', 300)
                )
                
                if event.type == 'payment_intent.succeeded':
                    payment = event.data.object
                    await self.record_transaction(
                        payment.id,
                        payment.amount / 100,
                        payment.currency,
                        'revenue',
                        'stripe',
                        payment.metadata
                    )
                    
            elif gateway == 'paypal':
                if payload.get('event_type') == 'PAYMENT.SALE.COMPLETED':
                    payment = payload.get('resource', {})
                    await self.record_transaction(
                        payment.get('id'),
                        float(payment.get('amount', {}).get('total', 0)),
                        payment.get('amount', {}).get('currency', 'USD'),
                        'revenue',
                        'paypal',
                        payment.get('metadata', {})
                    )
                    
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

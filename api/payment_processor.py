"""
Payment Processor - Handles Stripe/PayPal integrations and transaction processing.
"""
import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Optional

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentProcessor:
    """Handles payment processing and transaction recording."""
    
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        
    async def create_payment_intent(self, amount: float, currency: str, payment_method: str, metadata: Dict) -> Dict:
        """Create a payment intent with Stripe or PayPal."""
        try:
            amount_cents = int(amount * 100)
            
            if payment_method == "stripe":
                intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency.lower(),
                    metadata=metadata,
                    capture_method="automatic"
                )
                return {
                    "success": True,
                    "payment_intent_id": intent.id,
                    "client_secret": intent.client_secret
                }
                
            elif payment_method == "paypal":
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
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                
                if payment.create():
                    return {
                        "success": True,
                        "payment_id": payment.id,
                        "approval_url": next(link.href for link in payment.links if link.rel == "approval_url")
                    }
                else:
                    return {"success": False, "error": payment.error}
                    
            else:
                return {"success": False, "error": "Invalid payment method"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def record_transaction(self, payment_id: str, amount: float, currency: str, 
                               payment_method: str, metadata: Dict) -> Dict:
        """Record a successful transaction in the revenue system."""
        try:
            amount_cents = int(amount * 100)
            now = datetime.now(timezone.utc)
            
            await self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    '{currency}',
                    '{payment_method}',
                    '{json.dumps(metadata)}'::jsonb,
                    '{now.isoformat()}',
                    '{now.isoformat()}'
                )
            """)
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: Dict, signature: str, source: str) -> Dict:
        """Process payment webhooks from Stripe/PayPal."""
        try:
            if source == "stripe":
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                
                if event.type == "payment_intent.succeeded":
                    payment_intent = event.data.object
                    await self.record_transaction(
                        payment_intent.id,
                        payment_intent.amount / 100,
                        payment_intent.currency,
                        "stripe",
                        payment_intent.metadata
                    )
                    
            elif source == "paypal":
                if payload.get("event_type") == "PAYMENT.SALE.COMPLETED":
                    sale = payload.get("resource", {})
                    await self.record_transaction(
                        sale.get("id"),
                        float(sale.get("amount", {}).get("total", 0)),
                        sale.get("amount", {}).get("currency", "USD"),
                        "paypal",
                        sale.get("custom", {})
                    )
                    
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

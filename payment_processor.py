import os
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import execute_sql

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentProcessor:
    """Handles payment processing and webhook events"""
    
    def __init__(self):
        self.stripe = stripe
        self.paypal = paypalrestsdk
        
    async def create_payment_intent(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe payment intent"""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def create_paypal_order(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PayPal order"""
        try:
            payment = self.paypal.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get("description", ""),
                    "custom": json.dumps(metadata)
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if payment.create():
                return {"success": True, "payment_id": payment.id}
            return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def handle_stripe_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                await self._process_payment_success(
                    provider='stripe',
                    payment_id=payment_intent['id'],
                    amount=payment_intent['amount'] / 100,
                    currency=payment_intent['currency'],
                    metadata=payment_intent.get('metadata', {})
                )
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def handle_paypal_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal webhook events"""
        try:
            if payload.get('event_type') == 'PAYMENT.SALE.COMPLETED':
                sale = payload['resource']
                await self._process_payment_success(
                    provider='paypal',
                    payment_id=sale['id'],
                    amount=float(sale['amount']['total']),
                    currency=sale['amount']['currency'],
                    metadata=json.loads(sale.get('custom', '{}'))
                )
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _process_payment_success(self, provider: str, payment_id: str, amount: float, currency: str, metadata: Dict[str, Any]) -> None:
        """Record successful payment and trigger service delivery"""
        # Record the transaction
        await execute_sql(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), 'revenue', {int(amount * 100)}, '{currency.upper()}',
                '{provider}', '{json.dumps(metadata)}', NOW(), NOW()
            )
        """)
        
        # Trigger service delivery
        await self._deliver_service(metadata)
        
    async def _deliver_service(self, metadata: Dict[str, Any]) -> None:
        """Handle service delivery based on payment metadata"""
        # Implement your service delivery logic here
        # This could include:
        # - Granting access to features
        # - Sending digital products
        # - Triggering workflows
        pass

import os
import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentGateway:
    """Handle all payment processing through Stripe/PayPal APIs."""
    
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_API_KEY')
        self.stripe = stripe
        
    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new customer in payment system."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def create_subscription(
        self, 
        customer_id: str,
        price_id: str,
        trial_days: int = 0
    ) -> Dict:
        """Create recurring subscription."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def create_payment_intent(
        self,
        amount: int,
        currency: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create one-time payment intent."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True}
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process payment gateway webhooks."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return self._handle_payment_success(event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                return self._handle_subscription_payment(event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                return self._handle_subscription_canceled(event['data']['object'])
                
            return {"success": True, "handled": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_payment_success(self, payment_intent: Dict) -> Dict:
        """Process successful one-time payment."""
        # TODO: Trigger service delivery
        return {
            "success": True,
            "handled": True,
            "event": "payment_succeeded",
            "amount": payment_intent['amount'],
            "customer_id": payment_intent['customer']
        }
    
    def _handle_subscription_payment(self, invoice: Dict) -> Dict:
        """Process recurring subscription payment."""
        # TODO: Trigger service renewal
        return {
            "success": True,
            "handled": True,
            "event": "subscription_payment",
            "amount": invoice['amount_paid'],
            "customer_id": invoice['customer'],
            "subscription_id": invoice['subscription']
        }

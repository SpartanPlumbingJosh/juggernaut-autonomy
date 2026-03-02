import stripe
import logging
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
    def create_customer(self, email: str, name: str) -> Optional[str]:
        """Create a new customer in Stripe"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                description=f"Created on {datetime.utcnow().isoformat()}"
            )
            return customer.id
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            return None
            
    def create_payment_intent(self, amount: int, currency: str, customer_id: str) -> Optional[str]:
        """Create a payment intent for a customer"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                automatic_payment_methods={"enabled": True},
            )
            return intent.client_secret
        except stripe.error.StripeError as e:
            self.logger.error(f"Failed to create payment intent: {str(e)}")
            return None
            
    def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                self.logger.info(f"Payment succeeded: {payment_intent['id']}")
                return {
                    "status": "success",
                    "payment_id": payment_intent['id'],
                    "amount": payment_intent['amount'],
                    "currency": payment_intent['currency']
                }
                
            return {"status": "unhandled_event"}
            
        except stripe.error.StripeError as e:
            self.logger.error(f"Webhook error: {str(e)}")
            return {"status": "error", "message": str(e)}

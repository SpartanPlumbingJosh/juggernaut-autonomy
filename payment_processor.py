import logging
from typing import Dict, Optional
import stripe
from datetime import datetime

class PaymentProcessor:
    """Handles payment processing and product delivery"""
    
    def __init__(self, api_key: str):
        self.stripe = stripe
        self.stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
    def create_payment_intent(self, amount: int, currency: str, metadata: Dict) -> Dict:
        """Create a payment intent with Stripe"""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={"enabled": True}
            )
            return {"success": True, "payment_intent": intent}
        except Exception as e:
            self.logger.error(f"Payment intent creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def confirm_payment(self, payment_intent_id: str) -> Dict:
        """Confirm a payment was successful"""
        try:
            intent = self.stripe.PaymentIntent.retrieve(payment_intent_id)
            if intent.status == 'succeeded':
                return {
                    "success": True,
                    "payment_intent": intent,
                    "delivery_status": self.deliver_product(intent.metadata)
                }
            return {"success": False, "error": f"Payment not completed: {intent.status}"}
        except Exception as e:
            self.logger.error(f"Payment confirmation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def deliver_product(self, metadata: Dict) -> Dict:
        """Handle product delivery logic"""
        try:
            # TODO: Implement actual product delivery based on metadata
            # This could be email delivery, API call, etc.
            return {
                "success": True,
                "delivered_at": datetime.utcnow().isoformat(),
                "metadata": metadata
            }
        except Exception as e:
            self.logger.error(f"Product delivery failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                intent = event['data']['object']
                return self.confirm_payment(intent['id'])
                
            return {"success": False, "error": f"Unhandled event type: {event['type']}"}
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

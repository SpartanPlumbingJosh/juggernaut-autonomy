import stripe
from datetime import datetime
from typing import Dict, Optional

class PaymentProcessor:
    def __init__(self, api_key: str):
        self.stripe = stripe
        self.stripe.api_key = api_key

    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.utcnow().isoformat()}"
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a subscription for a customer."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "payment_intent": subscription.latest_invoice.payment_intent
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                return self._handle_payment_failure(event)
            
            return {"success": True, "handled": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_payment_success(self, event: Dict) -> Dict:
        """Handle successful payment event."""
        payment_intent = event['data']['object']
        return {
            "success": True,
            "handled": True,
            "event": "payment_success",
            "customer_id": payment_intent['customer'],
            "amount": payment_intent['amount'],
            "currency": payment_intent['currency']
        }

    def _handle_payment_failure(self, event: Dict) -> Dict:
        """Handle failed payment event."""
        invoice = event['data']['object']
        return {
            "success": True,
            "handled": True,
            "event": "payment_failure",
            "customer_id": invoice['customer'],
            "attempt_count": invoice['attempt_count'],
            "next_payment_attempt": invoice['next_payment_attempt']
        }

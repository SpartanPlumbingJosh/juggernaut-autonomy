import stripe
from typing import Any, Dict, Optional

class PaymentProcessor:
    """Handle payment processing and subscriptions."""
    
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_customer(self, email: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a subscription for a customer."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def record_payment(self, payment_intent_id: str) -> Dict[str, Any]:
        """Record a successful payment."""
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                "success": True,
                "amount": payment_intent.amount,
                "currency": payment_intent.currency,
                "customer_id": payment_intent.customer
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

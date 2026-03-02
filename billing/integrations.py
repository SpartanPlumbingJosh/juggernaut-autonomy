import stripe
from typing import Dict, Optional
from datetime import datetime

class BillingManager:
    """Handle billing operations and integrations."""
    
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key
        
    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe."""
        return stripe.Customer.create(
            email=email,
            name=name,
            description=f"Customer created on {datetime.utcnow().isoformat()}"
        )
        
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription."""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{
                'price': price_id
            }],
            expand=['latest_invoice.payment_intent']
        )
        
    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Optional[Dict]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return event
        except Exception as e:
            return None

from typing import Dict, Optional
from datetime import datetime, timedelta
import stripe

class PaymentProcessor:
    """Handle all payment operations with Stripe integration."""
    
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_customer(self, email: str, name: str) -> Dict:
        """Register new billing customer."""
        return stripe.Customer.create(
            email=email,
            name=name,
            description=f"Customer created on {datetime.utcnow().date()}"
        )
        
    def create_subscription(self, customer_id: str, plan_id: str) -> Dict:
        """Create recurring subscription."""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{"plan": plan_id}]
        )
        
    def charge_invoice(self, invoice_id: str) -> Dict:
        """Process invoice payment."""
        return stripe.Invoice.pay(invoice_id)
        
    def verify_payment(self, payment_intent_id: str) -> bool:
        """Verify payment was successful."""
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return intent.status == 'succeeded'

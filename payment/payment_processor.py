import stripe
from typing import Dict, Optional
from core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentProcessor:
    """Handle payment processing through Stripe"""
    
    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe"""
        return stripe.Customer.create(
            email=email,
            name=name,
            description=f"Customer for {settings.APP_NAME}"
        )
    
    def create_payment_intent(self, amount: int, currency: str, customer_id: str, 
                            metadata: Optional[Dict] = None) -> Dict:
        """Create a payment intent for a customer"""
        return stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            customer=customer_id,
            metadata=metadata or {},
            automatic_payment_methods={
                'enabled': True,
            },
        )
    
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a subscription for a customer"""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{
                'price': price_id,
            }],
            expand=['latest_invoice.payment_intent'],
        )

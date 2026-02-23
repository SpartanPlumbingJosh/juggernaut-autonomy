import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key: str):
        self.stripe = stripe
        self.stripe.api_key = api_key

    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe"""
        return self.stripe.Customer.create(
            email=email,
            name=name,
            description=f"Customer created on {datetime.utcnow().isoformat()}"
        )

    def create_payment_intent(
        self,
        amount: int,
        currency: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a payment intent for immediate capture"""
        intent = self.stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            customer=customer_id,
            metadata=metadata or {},
            capture_method='automatic'
        )
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "status": intent.status
        }

    def record_revenue_event(
        self,
        amount_cents: int,
        currency: str,
        source: str,
        metadata: Dict
    ) -> Dict:
        """Record a successful payment in our revenue system"""
        # In production, this would connect to your database
        return {
            "success": True,
            "amount_cents": amount_cents,
            "currency": currency,
            "source": source,
            "metadata": metadata,
            "recorded_at": datetime.utcnow().isoformat()
        }

    def process_payment(
        self,
        amount: int,
        currency: str,
        payment_method: str,
        customer_email: str,
        customer_name: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Complete payment processing flow"""
        try:
            # Create or get customer
            customer = self.create_customer(customer_email, customer_name)
            
            # Create payment intent
            intent = self.create_payment_intent(
                amount=amount,
                currency=currency,
                customer_id=customer.id,
                metadata=metadata
            )
            
            # Confirm payment (in production this would be async via webhook)
            confirmed = self.stripe.PaymentIntent.confirm(
                intent['payment_intent_id'],
                payment_method=payment_method
            )
            
            # Record revenue event
            if confirmed.status == 'succeeded':
                revenue_event = self.record_revenue_event(
                    amount_cents=amount,
                    currency=currency,
                    source="stripe",
                    metadata={
                        **metadata,
                        "payment_intent_id": intent['payment_intent_id'],
                        "customer_id": customer.id
                    }
                )
                return {
                    "success": True,
                    "payment_intent": intent,
                    "revenue_event": revenue_event
                }
            
            return {
                "success": False,
                "error": f"Payment failed with status: {confirmed.status}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

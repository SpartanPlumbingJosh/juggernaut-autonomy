import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Optional, List

class PaymentProcessor:
    """Handles payment processing integrations with Stripe/Paddle."""
    
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_SECRET_KEY")
        stripe.api_key = self.stripe_api_key
        
    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer": customer}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription for a customer."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {"success": True, "subscription": subscription}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def record_transaction(self, amount_cents: int, currency: str, source: str, 
                         metadata: Optional[Dict] = None) -> Dict:
        """Record a revenue transaction."""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                payment_method_types=['card'],
                metadata=metadata or {}
            )
            return {
                "success": True,
                "transaction_id": payment_intent.id,
                "amount_cents": amount_cents,
                "currency": currency,
                "source": source,
                "recorded_at": datetime.now(timezone.isoformat())
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def generate_invoice(self, customer_id: str, amount_cents: int, 
                        currency: str, description: str) -> Dict:
        """Generate an invoice for a customer."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                amount=amount_cents,
                currency=currency,
                description=description,
                auto_advance=True
            )
            return {"success": True, "invoice": invoice}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    def list_transactions(self, limit: int = 100) -> List[Dict]:
        """List recent transactions."""
        try:
            charges = stripe.Charge.list(limit=limit)
            return [{
                "id": charge.id,
                "amount_cents": charge.amount,
                "currency": charge.currency,
                "created": charge.created,
                "status": charge.status
            } for charge in charges.data]
        except stripe.error.StripeError as e:
            return []

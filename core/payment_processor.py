import stripe
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from decimal import Decimal

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_customer(self, email: str, name: str) -> Dict:
        """Create a new customer in Stripe"""
        return stripe.Customer.create(
            email=email,
            name=name,
            description=f"Customer created on {datetime.now().isoformat()}"
        )
        
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription"""
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            expand=["latest_invoice.payment_intent"]
        )
        
    def create_invoice(self, customer_id: str, amount: Decimal, currency: str = "usd") -> Dict:
        """Create an invoice for a customer"""
        return stripe.Invoice.create(
            customer=customer_id,
            auto_advance=True,
            collection_method="send_invoice",
            days_until_due=30,
            currency=currency,
            description=f"Invoice generated on {datetime.now().isoformat()}",
            metadata={"generated_at": datetime.now().isoformat()}
        )
        
    def record_payment(self, payment_intent_id: str) -> Dict:
        """Record a successful payment"""
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return {
            "payment_id": payment_intent.id,
            "amount": payment_intent.amount,
            "currency": payment_intent.currency,
            "status": payment_intent.status,
            "created": payment_intent.created
        }
        
    def get_upcoming_invoices(self, customer_id: str) -> List[Dict]:
        """Get upcoming invoices for a customer"""
        invoices = stripe.Invoice.upcoming(customer=customer_id)
        return [{
            "id": invoice.id,
            "amount_due": invoice.amount_due,
            "due_date": datetime.fromtimestamp(invoice.due_date) if invoice.due_date else None,
            "status": invoice.status
        } for invoice in invoices]
        
    def apply_tax(self, customer_id: str, tax_rate_id: str) -> Dict:
        """Apply tax rate to a customer"""
        return stripe.Customer.modify(
            customer_id,
            tax={"tax_rate": tax_rate_id}
        )

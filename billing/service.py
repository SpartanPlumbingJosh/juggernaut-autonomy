import stripe
import paypalrestsdk
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from billing.models import (
    PaymentMethod,
    SubscriptionPlan,
    Subscription,
    Invoice,
    PaymentMethodType
)

class BillingService:
    def __init__(self, stripe_api_key: str, paypal_client_id: str, paypal_secret: str):
        stripe.api_key = stripe_api_key
        paypalrestsdk.configure({
            "mode": "live",
            "client_id": paypal_client_id,
            "client_secret": paypal_secret
        })

    async def create_payment_method(self, type: PaymentMethodType, token: str) -> PaymentMethod:
        """Create a new payment method"""
        if type == PaymentMethodType.CARD:
            pm = stripe.PaymentMethod.create(
                type="card",
                card={"token": token}
            )
            return PaymentMethod(
                id=pm.id,
                type=PaymentMethodType.CARD,
                last4=pm.card.last4,
                brand=pm.card.brand,
                created_at=datetime.fromtimestamp(pm.created),
                is_default=False
            )
        elif type == PaymentMethodType.PAYPAL:
            # PayPal implementation
            pass

    async def create_subscription(self, plan_id: str, payment_method_id: str, trial_days: int = 0) -> Subscription:
        """Create a new subscription"""
        sub = stripe.Subscription.create(
            items=[{"price": plan_id}],
            payment_settings={"save_default_payment_method": "on_subscription"},
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"],
            trial_period_days=trial_days
        )
        return Subscription(
            id=sub.id,
            plan_id=plan_id,
            status=sub.status,
            current_period_start=datetime.fromtimestamp(sub.current_period_start),
            current_period_end=datetime.fromtimestamp(sub.current_period_end),
            cancel_at_period_end=sub.cancel_at_period_end,
            payment_method_id=payment_method_id,
            created_at=datetime.fromtimestamp(sub.created),
            updated_at=datetime.fromtimestamp(sub.created)
        )

    async def generate_invoice(self, subscription_id: str) -> Invoice:
        """Generate an invoice for a subscription"""
        invoice = stripe.Invoice.create(
            subscription=subscription_id,
            auto_advance=True
        )
        return Invoice(
            id=invoice.id,
            subscription_id=subscription_id,
            amount_due_cents=invoice.amount_due,
            amount_paid_cents=invoice.amount_paid,
            currency=invoice.currency,
            status=invoice.status,
            due_date=datetime.fromtimestamp(invoice.due_date),
            paid_at=datetime.fromtimestamp(invoice.status_transitions.paid_at) if invoice.status_transitions.paid_at else None,
            tax_cents=invoice.tax,
            total_cents=invoice.total,
            invoice_pdf=invoice.invoice_pdf,
            created_at=datetime.fromtimestamp(invoice.created)
        )

    async def apply_tax(self, amount_cents: int, country: str, state: str = None) -> Dict:
        """Calculate taxes for a given amount and jurisdiction"""
        tax_calculator = TaxCalculator()
        return tax_calculator.calculate_tax(amount_cents, country, state)

class TaxCalculator:
    """Handles tax calculations for different jurisdictions"""
    def calculate_tax(self, amount_cents: int, country: str, state: str = None) -> Dict:
        # Implement tax logic based on country/state
        # This would integrate with a tax API or local tax rules
        return {
            "tax_rate": 0.0,
            "tax_cents": 0,
            "total_cents": amount_cents
        }

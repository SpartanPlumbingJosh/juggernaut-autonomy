from __future__ import annotations
import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import stripe
import taxjar
from dataclasses import dataclass
from core.database import query_db, execute_sql


class PaymentProvider(enum.Enum):
    STRIPE = "stripe"
    PADDLE = "paddle"
    PAYPAL = "paypal"


@dataclass
class Customer:
    id: str
    email: str
    name: Optional[str]
    tax_id: Optional[str]
    address: Dict[str, str]
    metadata: Dict[str, Any]


@dataclass
class PaymentMethod:
    id: str
    type: str
    details: Dict[str, Any]
    is_default: bool


class PaymentService:

    def __init__(self, provider: PaymentProvider, api_key: str):
        self.provider = provider
        if provider == PaymentProvider.STRIPE:
            stripe.api_key = api_key
        # Initialize other providers here

    def create_customer(self, email: str, name: str = None) -> Customer:
        if self.provider == PaymentProvider.STRIPE:
            customer = stripe.Customer.create(
                email=email,
                name=name
            )
            return Customer(
                id=customer.id,
                email=email,
                name=name,
                tax_id=None,
                address={},
                metadata={}
            )
        raise NotImplementedError(f"Provider {self.provider} not implemented")

    async def create_payment_intent(self, amount: int, currency: str, customer_id: str) -> Dict[str, Any]:
        if self.provider == PaymentProvider.STRIPE:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency.lower(),
                customer=customer_id
            )
            return {
                "client_secret": intent.client_secret,
                "id": intent.id,
                "status": intent.status
            }
        raise NotImplementedError(f"Provider {self.provider} not implemented")

    async def create_subscription(self, customer_id: str, price_id: str, trial_days: int = 0) -> Dict[str, Any]:
        if self.provider == PaymentProvider.STRIPE:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days
            )
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
        raise NotImplementedError(f"Provider {self.provider} not implemented")

    def calculate_tax(self, customer: Customer, amount: float, currency: str) -> Dict[str, Any]:
        client = taxjar.Client(api_key=self.taxjar_api_key)
        try:
            tax = client.tax_for_order({
                'from_country': 'US',
                'from_zip': '94111',
                'from_state': 'CA',
                'to_country': customer.address.get('country'),
                'to_zip': customer.address.get('postal_code'),
                'to_state': customer.address.get('state'),
                'amount': amount,
                'shipping': 0,
                'line_items': [{
                    'quantity': 1,
                    'unit_price': amount,
                    'product_tax_code': 'digital'
                }]
            })
            return {
                "tax_rate": float(tax.rate),
                "tax_amount": float(tax.amount_to_collect),
                "jurisdictions": tax.jurisdictions._asdict()
            }
        except Exception as e:
            return {
                "error": str(e),
                "tax_rate": 0.0,
                "tax_amount": 0.0
            }

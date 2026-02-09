"""
Usage-Based Billing System - Tracks usage and calculates charges based on metered usage.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import stripe
from dataclasses import dataclass
from enum import Enum

class BillingPeriod(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

@dataclass
class UsageRecord:
    id: str
    customer_id: str
    subscription_id: str
    quantity: int
    timestamp: datetime
    metadata: Dict[str, str]

@dataclass
class Invoice:
    id: str
    customer_id: str
    amount_due: int
    currency: str
    period_start: datetime
    period_end: datetime
    lines: List[Dict]
    metadata: Dict[str, str]

class BillingManager:
    def __init__(self):
        self.stripe = stripe

    async def record_usage(self, customer_id: str, subscription_id: str, quantity: int, metadata: Dict[str, str]) -> UsageRecord:
        """Record usage for metered billing."""
        try:
            timestamp = datetime.utcnow()
            record = self.stripe.UsageRecord.create(
                subscription_item=subscription_id,
                quantity=quantity,
                timestamp=int(timestamp.timestamp()),
                metadata=metadata
            )
            return UsageRecord(
                id=record.id,
                customer_id=customer_id,
                subscription_id=subscription_id,
                quantity=quantity,
                timestamp=timestamp,
                metadata=metadata
            )
        except Exception as e:
            raise ValueError(f"Failed to record usage: {str(e)}")

    async def generate_invoice(self, customer_id: str, period: BillingPeriod) -> Invoice:
        """Generate an invoice for the billing period."""
        try:
            # Calculate period start/end
            end_time = datetime.utcnow()
            if period == BillingPeriod.DAILY:
                start_time = end_time - timedelta(days=1)
            elif period == BillingPeriod.WEEKLY:
                start_time = end_time - timedelta(weeks=1)
            elif period == BillingPeriod.MONTHLY:
                start_time = end_time - timedelta(days=30)
            elif period == BillingPeriod.YEARLY:
                start_time = end_time - timedelta(days=365)

            # Create invoice
            invoice = self.stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method="charge_automatically",
                metadata={
                    "billing_period": period.value
                }
            )
            return self._convert_stripe_invoice(invoice)
        except Exception as e:
            raise ValueError(f"Failed to generate invoice: {str(e)}")

    def _convert_stripe_invoice(self, stripe_invoice) -> Invoice:
        """Convert Stripe invoice to our model."""
        return Invoice(
            id=stripe_invoice.id,
            customer_id=stripe_invoice.customer,
            amount_due=stripe_invoice.amount_due,
            currency=stripe_invoice.currency,
            period_start=datetime.fromtimestamp(stripe_invoice.period_start),
            period_end=datetime.fromtimestamp(stripe_invoice.period_end),
            lines=[line.to_dict() for line in stripe_invoice.lines],
            metadata=stripe_invoice.metadata
        )

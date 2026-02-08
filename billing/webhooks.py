"""
Payment Processor Webhooks - Handle incoming payment events.
"""

from typing import Any, Dict

from billing.billing_service import BillingService

async def handle_stripe_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    billing = BillingService()
    return await billing.process_payment_webhook(payload)

async def handle_paypal_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process PayPal webhook events."""
    billing = BillingService()
    return await billing.process_payment_webhook(payload)

"""
Core billing infrastructure - Payment processing, subscriptions, metering and invoicing.

Key components:
- PaymentProcessor: Interface for Stripe/Paddle/etc
- SubscriptionManager: Handle plans, entitlements, renewals
- UsageMeter: Track and bill usage-based metrics
- InvoiceEngine: Generate and send invoices
- WebhookHandler: Process payment provider events
"""

__all__ = [
    "PaymentProcessor",
    "SubscriptionManager", 
    "UsageMeter",
    "InvoiceEngine",
    "WebhookHandler"
]

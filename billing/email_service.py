from typing import Dict, Optional
from .models import Invoice, Subscription

class EmailService:
    async def send_invoice(self, invoice: Invoice) -> None:
        """Send invoice email to customer"""
        pass

    async def send_payment_failed(self, subscription: Subscription, invoice: Invoice) -> None:
        """Send payment failed notification"""
        pass

    async def send_payment_success(self, subscription: Subscription, invoice: Invoice) -> None:
        """Send payment success notification"""
        pass

    async def send_subscription_canceled(self, subscription: Subscription) -> None:
        """Send subscription canceled notification"""
        pass

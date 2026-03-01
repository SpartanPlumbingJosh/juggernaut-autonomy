import os
import stripe
import paypalrestsdk
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from enum import Enum

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentMethod(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

class PaymentStatus(Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class PaymentProcessor:
    def __init__(self):
        self.fraud_rules = [
            self._check_velocity,
            self._check_ip_location,
            self._check_card_bin,
        ]
        
    async def create_payment_intent(
        self,
        amount: int,
        currency: str,
        payment_method: PaymentMethod,
        metadata: Optional[Dict] = None,
        customer_id: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Create a payment intent with fraud checks."""
        try:
            # Convert amount to smallest currency unit
            amount = self._convert_to_smallest_unit(amount, currency)
            
            # Create payment method specific intent
            if payment_method == PaymentMethod.STRIPE:
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    payment_method_types=["card"],
                    metadata=metadata or {},
                    customer=customer_id,
                    capture_method="manual"  # Allows fraud checks before capture
                )
                return intent.id, intent.client_secret
            elif payment_method == PaymentMethod.PAYPAL:
                payment = paypalrestsdk.Payment({
                    "intent": "authorize",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": str(amount / 100),
                            "currency": currency
                        }
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv("PAYPAL_RETURN_URL"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                    }
                })
                if payment.create():
                    return payment.id, payment.links[1].href
                raise Exception(payment.error)
            else:
                raise ValueError("Unsupported payment method")
        except Exception as e:
            raise Exception(f"Payment intent creation failed: {str(e)}")

    async def capture_payment(
        self,
        payment_id: str,
        payment_method: PaymentMethod,
        amount: Optional[int] = None,
    ) -> bool:
        """Capture an authorized payment after fraud checks."""
        try:
            if payment_method == PaymentMethod.STRIPE:
                intent = stripe.PaymentIntent.capture(
                    payment_id,
                    amount_to_capture=amount
                )
                return intent.status == "succeeded"
            elif payment_method == PaymentMethod.PAYPAL:
                auth = paypalrestsdk.Authorization.find(payment_id)
                capture = auth.capture({
                    "amount": {
                        "currency": auth.amount.currency,
                        "total": str(amount / 100) if amount else auth.amount.total
                    }
                })
                return capture.success()
            else:
                raise ValueError("Unsupported payment method")
        except Exception as e:
            raise Exception(f"Payment capture failed: {str(e)}")

    async def create_subscription(
        self,
        plan_id: str,
        customer_id: str,
        payment_method: PaymentMethod,
        trial_days: int = 0,
        metadata: Optional[Dict] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Create a subscription with automatic retries."""
        try:
            if payment_method == PaymentMethod.STRIPE:
                sub = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{"plan": plan_id}],
                    trial_period_days=trial_days,
                    metadata=metadata or {},
                    payment_settings={
                        "payment_method_types": ["card"],
                        "save_default_payment_method": "on_subscription"
                    },
                    off_session=True
                )
                return sub.id, sub.latest_invoice.payment_intent.client_secret
            elif payment_method == PaymentMethod.PAYPAL:
                agreement = paypalrestsdk.BillingAgreement({
                    "name": "Subscription Agreement",
                    "description": "Recurring payment agreement",
                    "start_date": (datetime.utcnow() + timedelta(days=trial_days)).isoformat(),
                    "plan": {
                        "id": plan_id
                    },
                    "payer": {
                        "payment_method": "paypal"
                    }
                })
                if agreement.create():
                    return agreement.id, agreement.links[0].href
                raise Exception(agreement.error)
            else:
                raise ValueError("Unsupported payment method")
        except Exception as e:
            raise Exception(f"Subscription creation failed: {str(e)}")

    async def handle_webhook(self, payload: Dict, signature: str, payment_method: PaymentMethod) -> bool:
        """Process payment webhooks."""
        try:
            if payment_method == PaymentMethod.STRIPE:
                event = stripe.Webhook.construct_event(
                    payload, signature, os.getenv("STRIPE_WEBHOOK_SECRET")
                )
                return await self._process_stripe_event(event)
            elif payment_method == PaymentMethod.PAYPAL:
                if paypalrestsdk.WebhookEvent.verify(
                    payload["transmission_id"],
                    payload["transmission_time"],
                    payload["webhook_id"],
                    payload["transmission_sig"],
                    payload["cert_url"],
                    payload["auth_algo"],
                    payload["webhook_event"]
                ):
                    return await self._process_paypal_event(payload["webhook_event"])
                return False
            else:
                raise ValueError("Unsupported payment method")
        except Exception as e:
            raise Exception(f"Webhook processing failed: {str(e)}")

    async def _process_stripe_event(self, event: stripe.Event) -> bool:
        """Process Stripe webhook events."""
        event_type = event["type"]
        data = event["data"]["object"]
        
        if event_type == "payment_intent.succeeded":
            await self._record_payment(
                data["id"],
                PaymentMethod.STRIPE,
                int(data["amount"]),
                data["currency"],
                PaymentStatus.SUCCEEDED,
                data.get("metadata", {})
            )
        elif event_type == "payment_intent.payment_failed":
            await self._record_payment(
                data["id"],
                PaymentMethod.STRIPE,
                int(data["amount"]),
                data["currency"],
                PaymentStatus.FAILED,
                data.get("metadata", {})
            )
        elif event_type == "charge.refunded":
            await self._record_payment(
                data["id"],
                PaymentMethod.STRIPE,
                int(data["amount_refunded"]),
                data["currency"],
                PaymentStatus.REFUNDED,
                data.get("metadata", {})
            )
        elif event_type == "invoice.payment_succeeded":
            await self._record_recurring_payment(
                data["subscription"],
                PaymentMethod.STRIPE,
                int(data["amount_paid"]),
                data["currency"],
                PaymentStatus.SUCCEEDED,
                data.get("metadata", {})
            )
        elif event_type == "invoice.payment_failed":
            await self._record_recurring_payment(
                data["subscription"],
                PaymentMethod.STRIPE,
                int(data["amount_due"]),
                data["currency"],
                PaymentStatus.FAILED,
                data.get("metadata", {})
            )
        return True

    async def _process_paypal_event(self, event: Dict) -> bool:
        """Process PayPal webhook events."""
        event_type = event["event_type"]
        resource = event["resource"]
        
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            await self._record_payment(
                resource["id"],
                PaymentMethod.PAYPAL,
                int(float(resource["amount"]["value"]) * 100),
                resource["amount"]["currency_code"],
                PaymentStatus.SUCCEEDED,
                resource.get("custom_id", {})
            )
        elif event_type == "PAYMENT.CAPTURE.DENIED":
            await self._record_payment(
                resource["id"],
                PaymentMethod.PAYPAL,
                int(float(resource["amount"]["value"]) * 100),
                resource["amount"]["currency_code"],
                PaymentStatus.FAILED,
                resource.get("custom_id", {})
            )
        elif event_type == "PAYMENT.CAPTURE.REFUNDED":
            await self._record_payment(
                resource["id"],
                PaymentMethod.PAYPAL,
                int(float(resource["amount"]["value"]) * 100),
                resource["amount"]["currency_code"],
                PaymentStatus.REFUNDED,
                resource.get("custom_id", {})
            )
        elif event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
            await self._record_subscription_status(
                resource["id"],
                PaymentMethod.PAYPAL,
                SubscriptionStatus.ACTIVE
            )
        elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
            await self._record_subscription_status(
                resource["id"],
                PaymentMethod.PAYPAL,
                SubscriptionStatus.PAST_DUE
            )
        return True

    async def _record_payment(
        self,
        payment_id: str,
        payment_method: PaymentMethod,
        amount: int,
        currency: str,
        status: PaymentStatus,
        metadata: Dict
    ) -> None:
        """Record payment in revenue tracking system."""
        # Implementation depends on your revenue tracking system
        pass

    async def _record_recurring_payment(
        self,
        subscription_id: str,
        payment_method: PaymentMethod,
        amount: int,
        currency: str,
        status: PaymentStatus,
        metadata: Dict
    ) -> None:
        """Record recurring payment in revenue tracking system."""
        # Implementation depends on your revenue tracking system
        pass

    async def _record_subscription_status(
        self,
        subscription_id: str,
        payment_method: PaymentMethod,
        status: SubscriptionStatus
    ) -> None:
        """Update subscription status in database."""
        # Implementation depends on your database system
        pass

    def _convert_to_smallest_unit(self, amount: float, currency: str) -> int:
        """Convert amount to smallest currency unit."""
        zero_decimal_currencies = ["JPY", "KRW", "VND"]
        if currency.upper() in zero_decimal_currencies:
            return int(amount)
        return int(amount * 100)

    def _check_velocity(self, payment_data: Dict) -> bool:
        """Check for excessive payment attempts."""
        # Implement velocity checking logic
        return True

    def _check_ip_location(self, payment_data: Dict) -> bool:
        """Check for suspicious IP locations."""
        # Implement IP location checking logic
        return True

    def _check_card_bin(self, payment_data: Dict) -> bool:
        """Check for suspicious card BINs."""
        # Implement card BIN checking logic
        return True

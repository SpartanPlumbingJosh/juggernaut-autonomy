"""
Payment Processor Module - Handles all payment integrations with vendors like Stripe/PayPal.
Includes error recovery, retry logic, and supports 24/7 operation.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
import stripe
import paypalrestsdk

class PaymentProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.stripe_key = config.get("stripe_secret_key")
        self.paypal_config = {
            "mode": config.get("paypal_mode", "sandbox"),
            "client_id": config.get("paypal_client_id"),
            "client_secret": config.get("paypal_client_secret")
        }
        self.max_retries = 3
        self.retry_delay = 1
        
        if self.stripe_key:
            stripe.api_key = self.stripe_key
        if all(self.paypal_config.values()):
            paypalrestsdk.configure(self.paypal_config)

    async def process_payment(self, method: str, details: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Process payment with automatic retry logic."""
        processor = {
            "stripe": self._process_stripe,
            "paypal": self._process_paypal
        }.get(method.lower())
        
        if not processor:
            return (False, {"error": "Unsupported payment method"})

        last_error = None
        for attempt in range(self.max_retries):
            try:
                receipt = await processor(details)
                return (True, receipt)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                continue
                
        return (False, {"error": f"Payment failed after {self.max_retries} attempts", "details": last_error})

    async def _process_stripe(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Process Stripe payment."""
        intent = stripe.PaymentIntent.create(
            amount=int(details["amount"] * 100),  # Convert to cents
            currency=details.get("currency", "usd"),
            metadata=details.get("metadata", {}),
            payment_method=details["payment_method_id"],
            confirmation_method="manual",
            confirm=True,
            off_session=True,
        )
        
        if intent.status == "succeeded":
            return {
                "transaction_id": intent.id,
                "amount": intent.amount / 100,
                "currency": intent.currency,
                "receipt_url": intent.charges.data[0].receipt_url
            }
            
        raise Exception(f"Stripe payment failed: {intent.last_payment_error or 'Unknown error'}")

    async def _process_paypal(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal payment."""
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": str(details["amount"]),
                    "currency": details.get("currency", "USD")
                }
            }]
        })
        
        if payment.create():
            return {
                "transaction_id": payment.id,
                "amount": float(payment.transactions[0].amount.total),
                "currency": payment.transactions[0].amount.currency,
                "links": [link.href for link in payment.links]
            }
            
        raise Exception(f"PayPal payment failed: {payment.error}")

    async def issue_refund(self, method: str, transaction_id: str, amount: float) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Issue refund with automatic retry logic."""
        refund_processor = {
            "stripe": self._refund_stripe,
            "paypal": self._refund_paypal
        }.get(method.lower())
        
        if not refund_processor:
            return (False, {"error": "Unsupported refund method"})

        for attempt in range(self.max_retries):
            try:
                return (True, await refund_processor(transaction_id, amount))
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return (False, {"error": str(e)})
                time.sleep(self.retry_delay * (attempt + 1))
                
        return (False, {"error": "Refund failed after max retries"})

    async def _refund_stripe(self, transaction_id: str, amount: float) -> Dict[str, Any]:
        refund = stripe.Refund.create(
            payment_intent=transaction_id,
            amount=int(amount * 100)  # Convert to cents
        )
        return refund.to_dict()

    async def _refund_paypal(self, transaction_id: str, amount: float) -> Dict[str, Any]:
        sale = paypalrestsdk.Sale.find(transaction_id)
        refund = sale.refund({
            "amount": {
                "total": str(amount),
                "currency": "USD"
            }
        })
        if refund.success():
            return {"status": "completed", "refund_id": refund.id}
        raise Exception(f"PayPal refund failed: {refund.error}")

    def validate_webhook(self, method: str, payload: Any, signature: str) -> bool:
        """Validate payment webhook signature."""
        validators = {
            "stripe": self._validate_stripe_webhook,
            "paypal": self._validate_paypal_webhook
        }
        validator = validators.get(method.lower())
        return validator(payload, signature) if validator else False

    def _validate_stripe_webhook(self, payload: Any, signature: str) -> bool:
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.stripe_webhook_secret
            )
            return True
        except Exception:
            return False

    def _validate_paypal_webhook(self, payload: Any, signature: str) -> bool:
        return paypalrestsdk.WebhookEvent.verify(
            payload["event_id"],
            self.paypal_webhook_id,
            payload
        )

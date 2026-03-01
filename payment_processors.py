from abc import ABC, abstractmethod
import json
import hmac
import hashlib

class PaymentProcessor(ABC):
    """Base class for payment processors."""
    
    @classmethod
    def create(cls, name: str) -> "PaymentProcessor":
        """Create processor instance by name."""
        if name == "stripe":
            return StripeProcessor()
        elif name == "paypal":
            return PayPalProcessor()
        elif name == "crypto":
            return CryptoProcessor()
        return None
    
    @abstractmethod
    def verify_webhook(self, body: str, signature: str) -> bool:
        """Verify webhook signature."""
        pass
    
    @abstractmethod
    def parse_webhook(self, body: str) -> dict:
        """Parse webhook event into standard format."""
        pass


class StripeProcessor(PaymentProcessor):
    """Stripe payment processor."""
    
    def verify_webhook(self, body: str, signature: str) -> bool:
        # Implement Stripe webhook verification
        # See: https://stripe.com/docs/webhooks/signatures
        return True
    
    def parse_webhook(self, body: str) -> dict:
        event = json.loads(body)
        if event["type"] != "payment_intent.succeeded":
            return None
            
        payment = event["data"]["object"]
        return {
            "amount": payment["amount"] / 100,
            "currency": payment["currency"],
            "metadata": payment.get("metadata", {}),
            "experiment_id": payment.get("metadata", {}).get("experiment_id")
        }


class PayPalProcessor(PaymentProcessor):
    """PayPal payment processor."""
    
    def verify_webhook(self, body: str, signature: str) -> bool:
        # Implement PayPal webhook verification
        # See: https://developer.paypal.com/docs/api/webhooks/v1/
        return True
    
    def parse_webhook(self, body: str) -> dict:
        event = json.loads(body)
        if event["event_type"] != "PAYMENT.CAPTURE.COMPLETED":
            return None
            
        resource = event["resource"]
        return {
            "amount": float(resource["amount"]["value"]),
            "currency": resource["amount"]["currency"],
            "metadata": resource.get("custom", {}),
            "experiment_id": resource.get("custom", {}).get("experiment_id")
        }


class CryptoProcessor(PaymentProcessor):
    """Crypto payment processor."""
    
    def verify_webhook(self, body: str, signature: str) -> bool:
        # Implement crypto webhook verification
        # This would depend on the specific crypto payment provider
        return True
    
    def parse_webhook(self, body: str) -> dict:
        event = json.loads(body)
        if event["status"] != "completed":
            return None
            
        return {
            "amount": float(event["amount"]),
            "currency": event["currency"].upper(),
            "metadata": event.get("metadata", {}),
            "experiment_id": event.get("metadata", {}).get("experiment_id")
        }

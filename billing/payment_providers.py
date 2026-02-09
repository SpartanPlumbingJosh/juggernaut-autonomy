import os
import stripe
import paddle
from typing import Dict, Any, Optional
from datetime import datetime

class PaymentProvider:
    """Base class for payment providers"""
    
    def __init__(self):
        self.configure()
        
    def configure(self):
        """Configure provider credentials"""
        raise NotImplementedError
        
    def create_customer(self, email: str, name: str = None) -> Dict[str, Any]:
        """Create a new customer"""
        raise NotImplementedError
        
    def create_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Create a new subscription"""
        raise NotImplementedError
        
    def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook event"""
        raise NotImplementedError
        
    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Get invoice details"""
        raise NotImplementedError
        
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription"""
        raise NotImplementedError
        
    def refund_payment(self, payment_id: str, amount: int = None) -> Dict[str, Any]:
        """Refund a payment"""
        raise NotImplementedError


class StripeProvider(PaymentProvider):
    """Stripe payment provider implementation"""
    
    def configure(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        
    def create_customer(self, email: str, name: str = None) -> Dict[str, Any]:
        return stripe.Customer.create(
            email=email,
            name=name
        )
        
    def create_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': plan_id}]
        )
        
    def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = stripe.Event.construct_from(payload, stripe.api_key)
        return self._process_event(event)
        
    def _process_event(self, event: stripe.Event) -> Dict[str, Any]:
        # Handle different webhook events
        pass
        
    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        return stripe.Invoice.retrieve(invoice_id)
        
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return stripe.Subscription.delete(subscription_id)
        
    def refund_payment(self, payment_id: str, amount: int = None) -> Dict[str, Any]:
        return stripe.Refund.create(
            payment_intent=payment_id,
            amount=amount
        )


class PaddleProvider(PaymentProvider):
    """Paddle payment provider implementation"""
    
    def configure(self):
        self.vendor_id = os.getenv('PADDLE_VENDOR_ID')
        self.vendor_auth_code = os.getenv('PADDLE_VENDOR_AUTH_CODE')
        
    def create_customer(self, email: str, name: str = None) -> Dict[str, Any]:
        # Paddle handles customer creation during checkout
        return {'email': email, 'name': name}
        
    def create_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        # Paddle uses checkout URLs
        return paddle.Checkout.generate_url({
            'product_id': plan_id,
            'customer_email': customer_id
        })
        
    def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._process_event(payload)
        
    def _process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        # Handle different webhook events
        pass
        
    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        return paddle.Order.get(invoice_id)
        
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return paddle.Subscription.cancel(subscription_id)
        
    def refund_payment(self, payment_id: str, amount: int = None) -> Dict[str, Any]:
        return paddle.Refund.create(
            payment_id=payment_id,
            amount=amount
        )

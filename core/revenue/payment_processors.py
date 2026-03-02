import os
import stripe
import paypalrestsdk
from typing import Dict, Optional, Union
from abc import ABC, abstractmethod

class PaymentProcessor(ABC):
    """Abstract base class for payment processors."""
    
    @abstractmethod
    def create_customer(self, email: str, payment_method: Dict) -> str:
        """Create a new customer in processor."""
        pass
    
    @abstractmethod
    def create_subscription(self, customer_id: str, plan_id: str) -> str:
        """Create subscription for customer."""
        pass
    
    @abstractmethod
    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        """Process incoming webhook events."""
        pass


class StripeProcessor(PaymentProcessor):
    """Stripe payment processor implementation."""
    
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_API_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
    def create_customer(self, email: str, payment_method: Dict) -> str:
        """Create Stripe customer with payment method."""
        customer = stripe.Customer.create(
            email=email,
            payment_method=payment_method['id'],
            invoice_settings={
                'default_payment_method': payment_method['id']
            }
        )
        return customer.id

    def create_subscription(self, customer_id: str, plan_id: str) -> str:
        """Create Stripe subscription."""
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"plan": plan_id}]
        )
        return subscription.id

    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        """Process Stripe webhook event."""
        event = stripe.Webhook.construct_event(
            payload, signature, self.webhook_secret
        )
        return self._process_stripe_event(event)
    
    def _process_stripe_event(self, event) -> Dict:
        """Process individual Stripe event types."""
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'invoice.paid':
            return self._handle_payment_success(data)
        elif event_type == 'invoice.payment_failed':
            return self._handle_payment_failure(data)
        elif event_type == 'customer.subscription.deleted':
            return self._handle_subscription_canceled(data)
        else:
            return {'status': 'unhandled_event', 'type': event_type}
    
    def _handle_payment_success(self, invoice) -> Dict:
        """Process successful payment."""
        # TODO: Implement revenue recognition and service delivery
        return {
            'status': 'processed',
            'type': 'payment_success',
            'amount': invoice['amount_paid'],
            'customer_id': invoice['customer']
        }


class PayPalProcessor(PaymentProcessor):
    """PayPal payment processor implementation."""
    
    def __init__(self):
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })
        
    def create_customer(self, email: str, payment_method: Dict) -> str:
        """Create PayPal billing agreement."""
        # PayPal implementation differs from Stripe
        raise NotImplementedError("PayPal customer creation needs implementation")
        
    def create_subscription(self, customer_id: str, plan_id: str) -> str:
        """Create PayPal subscription."""
        raise NotImplementedError("PayPal subscription creation needs implementation")


def get_payment_processor(name: str = 'stripe') -> Optional[PaymentProcessor]:
    """Factory method to get configured payment processor."""
    if name == 'stripe':
        return StripeProcessor()
    elif name == 'paypal':
        return PayPalProcessor()
    return None

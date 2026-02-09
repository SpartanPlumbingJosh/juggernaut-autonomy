"""
Payment gateway integrations for Stripe and Paddle.
Handles payment processing, webhooks, and customer management.
"""

from typing import Dict, Optional, List
import stripe
import paddle
from datetime import datetime
from dataclasses import dataclass

@dataclass
class PaymentMethod:
    id: str
    type: str
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    brand: Optional[str] = None

class PaymentGateway:
    """Base class for payment gateways"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> str:
        """Create a new customer"""
        raise NotImplementedError
        
    def add_payment_method(self, customer_id: str, payment_token: str) -> PaymentMethod:
        """Add a payment method for customer"""
        raise NotImplementedError
        
    def charge(self, customer_id: str, amount: int, currency: str, description: str) -> Dict:
        """Charge a customer"""
        raise NotImplementedError
        
    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        """Process webhook event"""
        raise NotImplementedError

class StripeGateway(PaymentGateway):
    """Stripe payment gateway implementation"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        stripe.api_key = api_key
        
    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> str:
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {}
        )
        return customer.id
        
    def add_payment_method(self, customer_id: str, payment_token: str) -> PaymentMethod:
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={"token": payment_token}
        )
        stripe.PaymentMethod.attach(
            payment_method.id,
            customer=customer_id
        )
        return PaymentMethod(
            id=payment_method.id,
            type=payment_method.type,
            last4=payment_method.card.last4,
            exp_month=payment_method.card.exp_month,
            exp_year=payment_method.card.exp_year,
            brand=payment_method.card.brand
        )
        
    def charge(self, customer_id: str, amount: int, currency: str, description: str) -> Dict:
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            customer=customer_id,
            description=description,
            confirm=True
        )
        return {
            "id": payment_intent.id,
            "status": payment_intent.status,
            "amount": payment_intent.amount,
            "currency": payment_intent.currency
        }
        
    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        event = stripe.Webhook.construct_event(
            payload, signature, self.webhook_secret
        )
        return event.to_dict()

class PaddleGateway(PaymentGateway):
    """Paddle payment gateway implementation"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        paddle.set_api_key(api_key)
        
    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> str:
        customer = paddle.Customer.create(
            email=email,
            name=name,
            custom_data=metadata or {}
        )
        return customer.id
        
    def add_payment_method(self, customer_id: str, payment_token: str) -> PaymentMethod:
        payment_method = paddle.PaymentMethod.create(
            customer_id=customer_id,
            payment_token=payment_token
        )
        return PaymentMethod(
            id=payment_method.id,
            type=payment_method.type
        )
        
    def charge(self, customer_id: str, amount: int, currency: str, description: str) -> Dict:
        charge = paddle.Charge.create(
            amount=amount,
            currency=currency,
            customer_id=customer_id,
            description=description
        )
        return {
            "id": charge.id,
            "status": charge.status,
            "amount": charge.amount,
            "currency": charge.currency
        }
        
    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        event = paddle.Webhook.construct_event(
            payload, signature, self.webhook_secret
        )
        return event.to_dict()

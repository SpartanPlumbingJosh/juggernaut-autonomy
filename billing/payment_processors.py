import stripe
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timedelta
import logging

from core.config import settings

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Base class for payment processors"""
    
    def __init__(self):
        self.client = None
        self.retry_policies = []
        
    def connect(self):
        raise NotImplementedError
        
    def create_customer(self, email: str, name: str, metadata: dict = None) -> Optional[str]:
        raise NotImplementedError
        
    def create_payment_method(self, customer_id: str, payment_details: dict) -> Optional[str]:
        raise NotImplementedError
        
    def charge(self, customer_id: str, amount: int, currency: str, description: str,
               capture: bool = True) -> Tuple[bool, Optional[Dict]]:
        raise NotImplementedError
        
    def create_subscription(self, customer_id: str, plan_id: str,
                           payment_method_id: str = None) -> Optional[str]:
        raise NotImplementedError
        
    def retry_failed_payment(self, charge_id: str):
        raise NotImplementedError
        
    def refund(self, charge_id: str, amount: int = None) -> bool:
        raise NotImplementedError
        
        
class StripePaymentProcessor(PaymentProcessor):
    """Stripe payment processor implementation"""
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.retry_policies = [
            # (delay_hours, max_attempts)
            (24, 3),  # First retry after 24h, up to 3 times
            (72, 2),   # Then every 72h, up to 2 times
        ]
    
    def connect(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.max_network_retries = 2
        self.client = stripe
        
    def create_customer(self, email: str, name: str, metadata: dict = None) -> Optional[str]:
        try:
            customer = self.client.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return customer.id
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return None
            
    def create_payment_method(self, customer_id: str, payment_details: dict) -> Optional[str]:
        try:
            payment_method = self.client.PaymentMethod.create(
                type="card",
                card=payment_details,
            )
            attach_result = self.client.PaymentMethod.attach(
                payment_method.id,
                customer=customer_id
            )
            return payment_method.id
        except Exception as e:
            logger.error(f"Failed to create payment method: {str(e)}")
            return None
            
    def charge(self, customer_id: str, amount: int, currency: str, description: str,
               capture: bool = True) -> Tuple[bool, Optional[Dict]]:
        try:
            intent = self.client.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                description=description,
                capture_method='automatic' if capture else 'manual'
            )
            return True, intent.to_dict()
        except stripe.error.CardError as e:
            logger.error(f"Card declined: {str(e)}")
            return False, {'error': str(e.user_message)}
        except Exception as e:
            logger.error(f"Payment failed: {str(e)}")
            return False, None
            
    def create_subscription(self, customer_id: str, plan_id: str,
                           payment_method_id: str = None) -> Optional[str]:
        try:
            subscription = self.client.Subscription.create(
                customer=customer_id,
                items=[{'price': plan_id}],
                default_payment_method=payment_method_id if payment_method_id else None,
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return subscription.id
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return None

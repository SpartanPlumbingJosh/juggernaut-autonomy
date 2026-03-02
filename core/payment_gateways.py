from typing import Dict, Any, Optional
import stripe
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PaymentGateway:
    """Base class for payment gateway integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def charge(self, amount: float, currency: str, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a payment"""
        raise NotImplementedError
        
    def refund(self, transaction_id: str, amount: float) -> Dict[str, Any]:
        """Process a refund"""
        raise NotImplementedError
        
    def create_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a customer record"""
        raise NotImplementedError
        
    def update_customer(self, customer_id: str, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update customer details"""
        raise NotImplementedError

class StripeGateway(PaymentGateway):
    """Stripe payment gateway implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        stripe.api_key = config['api_key']
        
    def charge(self, amount: float, currency: str, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Charge a customer using Stripe"""
        try:
            charge = stripe.Charge.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                source=customer_data['payment_source'],
                description=customer_data.get('description', ''),
                metadata=customer_data.get('metadata', {})
            )
            return {
                'success': True,
                'transaction_id': charge.id,
                'amount': charge.amount / 100,
                'currency': charge.currency,
                'status': charge.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe charge failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def refund(self, transaction_id: str, amount: float) -> Dict[str, Any]:
        """Process a refund through Stripe"""
        try:
            refund = stripe.Refund.create(
                charge=transaction_id,
                amount=int(amount * 100)
            )
            return {
                'success': True,
                'refund_id': refund.id,
                'amount': refund.amount / 100,
                'status': refund.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def create_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=customer_data['email'],
                name=customer_data.get('name'),
                phone=customer_data.get('phone'),
                metadata=customer_data.get('metadata', {})
            )
            return {
                'success': True,
                'customer_id': customer.id,
                'created': datetime.fromtimestamp(customer.created)
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def update_customer(self, customer_id: str, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update Stripe customer details"""
        try:
            customer = stripe.Customer.modify(
                customer_id,
                **customer_data
            )
            return {
                'success': True,
                'customer_id': customer.id,
                'updated': datetime.fromtimestamp(customer.updated)
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer update failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

def get_payment_gateway(gateway_name: str, config: Dict[str, Any]) -> PaymentGateway:
    """Factory method to get payment gateway instance"""
    gateways = {
        'stripe': StripeGateway
    }
    if gateway_name not in gateways:
        raise ValueError(f"Unsupported payment gateway: {gateway_name}")
    return gateways[gateway_name](config)

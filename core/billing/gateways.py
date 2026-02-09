from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import stripe
import paypalrestsdk

class PaymentGateway(ABC):
    """Abstract base class for payment gateways"""
    
    @abstractmethod
    def create_payment_intent(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def capture_payment(self, payment_id: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def create_subscription(self, plan_id: str, customer_id: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        pass

class StripeGateway(PaymentGateway):
    """Stripe payment gateway implementation"""
    
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    def create_payment_intent(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                metadata=metadata,
                capture_method='manual'
            )
            return {
                'success': True,
                'payment_id': intent.id,
                'client_secret': intent.client_secret
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def capture_payment(self, payment_id: str) -> Dict[str, Any]:
        try:
            intent = stripe.PaymentIntent.capture(payment_id)
            return {
                'success': True,
                'status': intent.status,
                'amount': intent.amount / 100
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> Dict[str, Any]:
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_id,
                amount=int(amount * 100) if amount else None
            )
            return {
                'success': True,
                'status': refund.status,
                'amount': refund.amount / 100
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_subscription(self, plan_id: str, customer_id: str) -> Dict[str, Any]:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'plan': plan_id}],
                expand=['latest_invoice.payment_intent']
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'latest_payment_intent': subscription.latest_invoice.payment_intent.id
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                'success': True,
                'status': subscription.status
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }

class PayPalGateway(PaymentGateway):
    """PayPal payment gateway implementation"""
    
    def __init__(self, client_id: str, client_secret: str):
        paypalrestsdk.configure({
            "mode": "live",
            "client_id": client_id,
            "client_secret": client_secret
        })
    
    def create_payment_intent(self, amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        payment = paypalrestsdk.Payment({
            "intent": "authorize",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": str(amount),
                    "currency": currency
                },
                "description": metadata.get('description', '')
            }]
        })
        
        if payment.create():
            return {
                'success': True,
                'payment_id': payment.id,
                'approval_url': next(link.href for link in payment.links if link.rel == 'approval_url')
            }
        else:
            return {
                'success': False,
                'error': payment.error
            }
    
    def capture_payment(self, payment_id: str) -> Dict[str, Any]:
        payment = paypalrestsdk.Payment.find(payment_id)
        if payment.execute({"payer_id": payment.payer.payer_info.payer_id}):
            return {
                'success': True,
                'status': payment.state,
                'amount': float(payment.transactions[0].amount.total)
            }
        else:
            return {
                'success': False,
                'error': payment.error
            }
    
    def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> Dict[str, Any]:
        sale = paypalrestsdk.Sale.find(payment_id)
        refund = sale.refund({
            "amount": {
                "total": str(amount) if amount else str(sale.amount.total),
                "currency": sale.amount.currency
            }
        })
        
        if refund.success():
            return {
                'success': True,
                'status': refund.state,
                'amount': float(refund.amount.total)
            }
        else:
            return {
                'success': False,
                'error': refund.error
            }
    
    def create_subscription(self, plan_id: str, customer_id: str) -> Dict[str, Any]:
        # PayPal implementation would require creating billing agreement
        # This is a simplified version
        return {
            'success': False,
            'error': 'PayPal subscriptions not implemented'
        }
    
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return {
            'success': False,
            'error': 'PayPal subscriptions not implemented'
        }

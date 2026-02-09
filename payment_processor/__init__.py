"""
Payment Processor Module - Handles Stripe/PayPal integrations and transaction processing.
"""
import os
import stripe
import paypalrestsdk
from typing import Dict, Optional, Union
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentProcessor:
    """Handles payment processing across multiple providers."""
    
    @staticmethod
    async def create_payment_intent(
        amount: int,
        currency: str = 'usd',
        payment_method: str = 'stripe',
        metadata: Optional[Dict] = None
    ) -> Dict[str, Union[str, bool]]:
        """Create a payment intent with the specified provider."""
        try:
            if payment_method == 'stripe':
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    metadata=metadata or {},
                    automatic_payment_methods={"enabled": True},
                )
                return {
                    'success': True,
                    'client_secret': intent.client_secret,
                    'payment_id': intent.id
                }
            elif payment_method == 'paypal':
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount/100:.2f}",
                            "currency": currency.upper()
                        }
                    }],
                    "redirect_urls": {
                        "return_url": os.getenv('PAYPAL_RETURN_URL'),
                        "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                    }
                })
                if payment.create():
                    return {
                        'success': True,
                        'approval_url': next(
                            link.href for link in payment.links 
                            if link.method == "REDIRECT"
                        ),
                        'payment_id': payment.id
                    }
                raise Exception(payment.error)
            raise ValueError("Unsupported payment method")
        except Exception as e:
            logger.error(f"Payment creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def capture_payment(
        payment_id: str,
        payment_method: str = 'stripe',
        amount: Optional[int] = None
    ) -> Dict[str, Union[str, bool]]:
        """Capture an authorized payment."""
        try:
            if payment_method == 'stripe':
                intent = stripe.PaymentIntent.capture(payment_id)
                return {
                    'success': True,
                    'amount_captured': intent.amount_received,
                    'currency': intent.currency
                }
            elif payment_method == 'paypal':
                payment = paypalrestsdk.Payment.find(payment_id)
                if payment.execute({"payer_id": payment.payer.payer_info.payer_id}):
                    return {
                        'success': True,
                        'amount_captured': int(float(payment.transactions[0].amount.total) * 100),
                        'currency': payment.transactions[0].amount.currency
                    }
                raise Exception(payment.error)
            raise ValueError("Unsupported payment method")
        except Exception as e:
            logger.error(f"Payment capture failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def create_subscription(
        customer_id: str,
        plan_id: str,
        payment_method: str = 'stripe',
        metadata: Optional[Dict] = None
    ) -> Dict[str, Union[str, bool]]:
        """Create a recurring subscription."""
        try:
            if payment_method == 'stripe':
                sub = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{'plan': plan_id}],
                    metadata=metadata or {},
                    expand=['latest_invoice.payment_intent']
                )
                return {
                    'success': True,
                    'subscription_id': sub.id,
                    'status': sub.status,
                    'current_period_end': sub.current_period_end
                }
            raise ValueError("PayPal subscriptions not yet implemented")
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def record_transaction(
        payment_id: str,
        amount: int,
        currency: str,
        customer_id: str,
        product_id: str,
        payment_method: str,
        transaction_type: str = 'revenue'
    ) -> Dict[str, Union[str, bool]]:
        """Record a completed transaction in the revenue system."""
        try:
            # This would connect to your database to record the transaction
            # For now we'll return a mock response
            return {
                'success': True,
                'transaction_id': f"txn_{payment_id[:8]}",
                'recorded_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Transaction recording failed: {str(e)}")
            return {'success': False, 'error': str(e)}

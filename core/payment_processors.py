"""
Integration with payment processors like Stripe/PayPal.
Handles tokenization, charging, refunds and payment method management.
"""
import logging
from typing import Dict, Optional
import stripe  # Make sure to install stripe package

from dataclasses import dataclass


@dataclass
class PaymentMethod:
    id: str
    type: str  # "card", "bank", "paypal", etc
    last4: Optional[str] = None
    brand: Optional[str] = None
    expiry_month: Optional[int] = None
    expiry_year: Optional[int] = None


class PaymentProcessor:
    def __init__(self, api_key: str):
        self.logger = logging.getLogger("payments")
        stripe.api_key = api_key
    
    def create_customer(self, customer_data: Dict) -> Dict:
        """Create a customer record in the payment processor"""
        try:
            customer = stripe.Customer.create(
                email=customer_data.get('email'),
                name=customer_data.get('name'),
                metadata={
                    'internal_customer_id': customer_data.get('customer_id')
                }
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_payment_method(
        self,
        payment_data: Dict,
        customer_id: str = None
    ) -> Dict:
        """Tokenize a payment method"""
        try:
            # For cards
            if payment_data['type'] == 'card':
                pm = stripe.PaymentMethod.create(
                    type='card',
                    card={
                        'number': payment_data['number'],
                        'exp_month': payment_data['exp_month'],
                        'exp_year': payment_data['exp_year'],
                        'cvc': payment_data['cvc']
                    }
                )
                
                # Attach to customer if provided
                if customer_id:
                    stripe.PaymentMethod.attach(
                        pm.id,
                        customer=customer_id
                    )
                
                # Return enriched payment method info
                return {
                    "success": True,
                    "payment_method": PaymentMethod(
                        id=pm.id,
                        type="card",
                        last4=pm.card.last4,
                        brand=pm.card.brand,
                        expiry_month=pm.card.exp_month,
                        expiry_year=pm.card.exp_year
                    )
                }
            
            # Other payment methods could be implemented similarly
            
        except Exception as e:
            self.logger.error(f"Payment method creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def charge_payment(
        self,
        amount_cents: int,
        payment_method_id: str,
        invoice_id: str,
        currency: str = "usd"
    ) -> Dict:
        """Charge a payment method via processor"""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                payment_method=payment_method_id,
                confirmation_method='automatic',
                confirm=True,
                metadata={'invoice_id': invoice_id}
            )
            
            return {
                "success": True,
                "payment_id": payment_intent.id,
                "status": payment_intent.status,
                "receipt_url": payment_intent.charges.data[0].receipt_url
            }
        except Exception as e:
            self.logger.error(f"Payment charge failed: {str(e)}")
            return {"success": False, "error": str(e)}


class SubscriptionManager:
    """Manages recurring subscriptions through payment processor"""
    def __init__(self, api_key: str):
        self.stripe = stripe
        self.stripe.api_key = api_key
    
    def create_subscription(
        self, 
        customer_id: str,
        price_id: str,
        payment_method_id: str
    ) -> Dict:
        """Create a recurring subscription"""
        try:
            # Attach payment method to customer
            self.stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default payment method
            self.stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            
            # Create subscription
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                expand=['latest_invoice.payment_intent']
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

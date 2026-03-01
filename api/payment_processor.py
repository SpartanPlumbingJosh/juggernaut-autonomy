"""
Payment Processor - Handles Stripe/PayPal integrations and payment processing.
"""
import os
import stripe
import paypalrestsdk
from typing import Dict, Optional
from datetime import datetime

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentProcessor:
    """Handles payment processing across multiple gateways."""
    
    def __init__(self):
        self.gateways = {
            'stripe': self._process_stripe_payment,
            'paypal': self._process_paypal_payment
        }
    
    async def process_payment(self, gateway: str, amount: float, currency: str, 
                            customer_data: Dict, metadata: Optional[Dict] = None) -> Dict:
        """Process payment through specified gateway."""
        processor = self.gateways.get(gateway.lower())
        if not processor:
            return {"success": False, "error": "Unsupported payment gateway"}
        
        try:
            return await processor(amount, currency, customer_data, metadata or {})
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _process_stripe_payment(self, amount: float, currency: str, 
                                    customer_data: Dict, metadata: Dict) -> Dict:
        """Process payment through Stripe."""
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)
            
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                payment_method_types=['card'],
                receipt_email=customer_data.get('email'),
                metadata=metadata
            )
            
            return {
                "success": True,
                "payment_id": intent.id,
                "client_secret": intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": intent.status
            }
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    async def _process_paypal_payment(self, amount: float, currency: str,
                                    customer_data: Dict, metadata: Dict) -> Dict:
        """Process payment through PayPal."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get('description', 'Payment')
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            
            if payment.create():
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "approval_url": next(link.href for link in payment.links if link.method == "REDIRECT"),
                    "amount": amount,
                    "currency": currency,
                    "status": payment.state
                }
            else:
                return {"success": False, "error": payment.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

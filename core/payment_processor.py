import stripe
import paypalrestsdk
import logging
from typing import Dict, Optional, Union
from datetime import datetime, timezone

class PaymentProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.stripe_key = config.get('stripe_secret_key')
        self.paypal_config = {
            'mode': config.get('paypal_mode', 'sandbox'),
            'client_id': config.get('paypal_client_id'),
            'client_secret': config.get('paypal_secret')
        }
        
        if self.stripe_key:
            stripe.api_key = self.stripe_key
            
        if all(self.paypal_config.values()):
            paypalrestsdk.configure(**self.paypal_config)

    async def process_payment(
        self, 
        amount: float,
        currency: str,
        customer_email: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Union[str, bool]]:
        """Process payment through Stripe or PayPal."""
        try:
            amount_cents = int(amount * 100)  # Convert to smallest currency unit
            
            if self.stripe_key:
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency.lower(),
                    description=description,
                    receipt_email=customer_email,
                    metadata=metadata or {},
                    automatic_payment_methods={"enabled": True},
                )
                
                return {
                    "success": True,
                    "payment_id": payment_intent.id,
                    "payment_method": "stripe",
                    "amount_cents": amount_cents,
                    "currency": currency,
                }
           
            elif all(self.paypal_config.values()):
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {"payment_method": "paypal"},
                    "transactions": [{
                        "amount": {
                            "total": f"{amount:.2f}",
                            "currency": currency.upper()
                        },
                        "description": description
                    }],
                    "redirect_urls": {
                        "return_url": config.get('paypal_return_url'),
                        "cancel_url": config.get('paypal_cancel_url')
                    }
                })
                
                if payment.create():
                    return {
                        "success": True,
                        "payment_id": payment.id,
                        "payment_method": "paypal",
                        "amount_cents": amount_cents,
                        "currency": currency,
                        "approval_url": next(
                            link.href for link in payment.links 
                            if link.method == "REDIRECT"
                        )
                    }
                
            return self._log_failure("No valid payment processor configured")
            
        except Exception as e:
            return self._log_failure(f"Payment processing failed: {str(e)}")

    def _log_failure(self, error_msg: str) -> Dict[str, Union[str, bool]]:
        logging.error(error_msg)
        return {"success": False, "error": error_msg}

    async def verify_payment(self, payment_id: str, provider: str) -> bool:
        """Verify payment was completed successfully."""
        try:
            if provider == "stripe" and self.stripe_key:
                intent = stripe.PaymentIntent.retrieve(payment_id)
                return intent.status == "succeeded"
            
            elif provider == "paypal" and all(self.paypal_config.values()):
                payment = paypalrestsdk.Payment.find(payment_id)
                return payment.state == "approved"
                
            return False
            
        except Exception as e:
            logging.error(f"Payment verification failed: {str(e)}")
            return False

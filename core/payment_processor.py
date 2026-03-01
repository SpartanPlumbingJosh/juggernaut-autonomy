"""
Payment processing integration handling Stripe and PayPal transactions.
"""
import json
import logging
from typing import Dict, Any, Optional
import stripe
import paypalrestsdk

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.stripe_key = config.get("stripe_secret_key")
        self.paypal_config = config.get("paypal", {})
        
        if self.stripe_key:
            stripe.api_key = self.stripe_key
            
        if self.paypal_config:
            paypalrestsdk.configure({
                "mode": self.paypal_config.get("mode", "sandbox"),
                "client_id": self.paypal_config["client_id"],
                "client_secret": self.paypal_config["client_secret"]
            })

    async def process_payment(self, 
                            amount_cents: int, 
                            currency: str, 
                            payment_method: str, 
                            metadata: Dict[str, Any],
                            customer_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process payment through configured gateway.
        Returns payment status and transaction details.
        """
        try:
            if payment_method.lower() == "stripe" and self.stripe_key:
                return await self._process_stripe_payment(
                    amount_cents, 
                    currency,
                    metadata,
                    customer_details
                )
            elif payment_method.lower() == "paypal" and self.paypal_config:
                return await self._process_paypal_payment(
                    amount_cents, 
                    currency,
                    metadata
                )
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")
                
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "transaction_id": None
            }

    async def _process_stripe_payment(self, 
                                    amount_cents: int,
                                    currency: str,
                                    metadata: Dict[str, Any],
                                    customer_details: Dict[str, Any]) -> Dict[str, Any]:
        """Handle stripe payment processing"""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                receipt_email=customer_details.get("email"),
                description=metadata.get("description", "Revenue automation payment")
            )
            
            return {
                "status": "succeeded",
                "transaction_id": payment_intent.id,
                "payment_method": "stripe",
                "amount_cents": amount_cents,
                "currency": currency,
                "metadata": metadata
            }
            
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")

    async def _process_paypal_payment(self,
                                    amount_cents: int,
                                    currency: str,
                                    metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Handle PayPal payment processing"""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": f"{amount_cents/100:.2f}",
                        "currency": currency.upper()
                    },
                    "description": metadata.get("description", "Revenue automation payment")
                }]
            })
            
            if payment.create():
                return {
                    "status": "succeeded", 
                    "transaction_id": payment.id,
                    "payment_method": "paypal",
                    "amount_cents": amount_cents,
                    "currency": currency,
                    "metadata": metadata
                }
            else:
                raise Exception(f"PayPal error: {payment.error}")
                
        except Exception as e:
            raise Exception(f"PayPal processing error: {str(e)}")

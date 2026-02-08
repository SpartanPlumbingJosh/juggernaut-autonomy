"""
Payment Processor - Handle payment transactions and integrations.

Supports:
- Stripe payments
- PayPal payments
- Manual payments
"""

import os
import stripe
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        self.stripe_key = os.getenv("STRIPE_SECRET_KEY")
        if self.stripe_key:
            stripe.api_key = self.stripe_key

    async def process_payment(self, 
                            amount: float, 
                            currency: str, 
                            payment_method: str,
                            metadata: Optional[Dict] = None) -> Dict:
        """
        Process a payment transaction.
        
        Args:
            amount: Amount to charge
            currency: Currency code (e.g. 'USD')
            payment_method: Payment method type (stripe, paypal, manual)
            metadata: Additional transaction metadata
            
        Returns:
            Dict with payment status and details
        """
        try:
            if payment_method == "stripe":
                if not self.stripe_key:
                    raise ValueError("Stripe not configured")
                    
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency=currency.lower(),
                    metadata=metadata or {}
                )
                return {
                    "status": "success",
                    "payment_id": intent.id,
                    "client_secret": intent.client_secret
                }
                
            elif payment_method == "paypal":
                # PayPal integration placeholder
                return {
                    "status": "pending",
                    "payment_id": "paypal_placeholder",
                    "approval_url": "https://paypal.com/checkout"
                }
                
            elif payment_method == "manual":
                return {
                    "status": "requires_action",
                    "payment_id": "manual_placeholder",
                    "instructions": "Please contact support for payment details"
                }
                
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")
                
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    async def capture_payment(self, payment_id: str) -> Dict:
        """
        Capture a previously authorized payment.
        """
        try:
            if payment_id.startswith("pi_"):  # Stripe payment
                intent = stripe.PaymentIntent.capture(payment_id)
                return {
                    "status": "success",
                    "amount_received": intent.amount_received / 100.0
                }
            else:
                return {
                    "status": "success",
                    "message": "Payment captured"
                }
        except Exception as e:
            logger.error(f"Payment capture failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

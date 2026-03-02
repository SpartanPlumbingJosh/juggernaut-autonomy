import logging
from typing import Dict, Optional
from datetime import datetime
from decimal import Decimal

import stripe
from aiohttp import ClientSession

from core.config import settings

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handles payment processing at scale with Stripe integration."""
    
    def __init__(self):
        self.stripe_key = settings.STRIPE_SECRET_KEY
        stripe.api_key = self.stripe_key
        
    async def process_payment(
        self,
        amount: Decimal,
        currency: str,
        payment_method_id: str,
        customer_id: str,
        description: str = "",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Process payment attempt"""
        try:
            # Create payment intent
            intent = await stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                payment_method=payment_method_id,
                customer=customer_id,
                description=description,
                metadata=metadata or {},
                confirm=True,
                off_session=True
            )
            
            # Record transaction
            await self._record_transaction(
                intent.id,
                amount,
                currency,
                intent.status,
                customer_id,
                metadata
            )

            return {
                "success": True,
                "payment_id": intent.id,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment failed: {str(e)}")
            return self._handle_payment_error(e)
            
    async def _handle_payment_error(self, error) -> Dict:
        """Standard error response format"""
        return {
            "success": False,
            "error_type": str(error.__class__.__name__),
            "error_code": getattr(error, "code", None),
            "message": str(error)
        }

from __future__ import annotations
import stripe
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from decimal import Decimal

class PaymentProcessor:
    """Handles all payment processing operations with Stripe."""
    
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
    def create_customer(self, email: str, **metadata) -> Dict[str, Any]:
        """Create a new customer in Stripe."""
        try:
            customer = stripe.Customer.create(
                email=email,
                metadata=metadata
            )
            self.logger.info(f"Created customer {customer.id}")
            return {"success": True, "customer": customer}
        except stripe.error.StripeError as e:
            self.logger.error(f"Customer creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a recurring subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{
                    'price': price_id
                }],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            self.logger.info(f"Created subscription {subscription.id}")
            return {"success": True, "subscription": subscription}
        except stripe.error.StripeError as e:
            self.logger.error(f"Subscription creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def record_charge(
        self, 
        amount: Decimal, 
        currency: str = "usd",
        description: str = "",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Record a one-time charge."""
        try:
            amount_cents = int(amount * 100)
            charge = stripe.Charge.create(
                amount=amount_cents,
                currency=currency,
                description=description,
                metadata=metadata or {}
            )
            self.logger.info(f"Processed charge {charge.id} for ${amount}")
            return {
                "success": True,
                "charge_id": charge.id,
                "amount_cents": amount_cents
            }
        except stripe.error.StripeError as e:
            self.logger.error(f"Charge failed: {str(e)}")
            return {"success": False, "error": str(e)}

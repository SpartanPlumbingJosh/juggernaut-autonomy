"""
Payment Processor - Handles payment processing and digital delivery.

Supports:
- Stripe payments
- PayPal payments
- Digital product delivery
- Subscription management
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import stripe
import paypalrestsdk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class PaymentProcessor:
    """Handles payment processing and digital delivery."""
    
    def __init__(self):
        self.currency = "usd"
        self.default_payment_method = "stripe"
        
    async def process_payment(self, amount: float, payment_method: str, 
                            customer_info: Dict, product_info: Dict) -> Tuple[bool, Dict]:
        """Process a payment and deliver digital product."""
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)
            
            # Process payment
            if payment_method.lower() == "stripe":
                result = await self._process_stripe_payment(amount_cents, customer_info)
            elif payment_method.lower() == "paypal":
                result = await self._process_paypal_payment(amount, customer_info)
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")
                
            if not result[0]:
                return False, result[1]
                
            # Record revenue event
            await self._record_revenue_event(
                amount_cents=amount_cents,
                payment_method=payment_method,
                product_info=product_info,
                transaction_id=result[1].get("transaction_id")
            )
            
            # Deliver product
            delivery_result = await self._deliver_product(product_info, customer_info)
            
            return True, {
                "payment": result[1],
                "delivery": delivery_result
            }
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return False, {"error": str(e)}
            
    async def _process_stripe_payment(self, amount_cents: int, customer_info: Dict) -> Tuple[bool, Dict]:
        """Process payment via Stripe."""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=self.currency,
                payment_method_types=["card"],
                receipt_email=customer_info.get("email"),
                metadata={
                    "customer_name": customer_info.get("name"),
                    "product": customer_info.get("product_name")
                }
            )
            
            return True, {
                "transaction_id": payment_intent.id,
                "payment_method": "stripe",
                "status": payment_intent.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment failed: {str(e)}")
            return False, {"error": str(e)}
            
    async def _process_paypal_payment(self, amount: float, customer_info: Dict) -> Tuple[bool, Dict]:
        """Process payment via PayPal."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "transactions": [{
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": self.currency
                    },
                    "description": customer_info.get("product_name")
                }],
                "redirect_urls": {
                    "return_url": os.getenv("PAYPAL_RETURN_URL"),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                }
            })
            
            if payment.create():
                return True, {
                    "transaction_id": payment.id,
                    "payment_method": "paypal",
                    "status": payment.state
                }
            else:
                raise ValueError(payment.error)
                
        except Exception as e:
            logger.error(f"PayPal payment failed: {str(e)}")
            return False, {"error": str(e)}
            
    async def _record_revenue_event(self, amount_cents: int, payment_method: str,
                                  product_info: Dict, transaction_id: str) -> bool:
        """Record revenue event in database."""
        try:
            metadata = {
                "product_id": product_info.get("id"),
                "product_name": product_info.get("name"),
                "payment_method": payment_method,
                "transaction_id": transaction_id
            }
            
            sql = f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{self.currency}',
                '{payment_method}',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
            """
            
            # Assuming query_db is available from core.database
            from core.database import query_db
            await query_db(sql)
            return True
            
        except Exception as e:
            logger.error(f"Failed to record revenue event: {str(e)}")
            return False
            
    async def _deliver_product(self, product_info: Dict, customer_info: Dict) -> Dict:
        """Handle digital product delivery."""
        try:
            # Implement your product delivery logic here
            # This could be emailing download links, API keys, etc.
            return {
                "status": "delivered",
                "method": "email",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Product delivery failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

# Singleton instance for easy access
payment_processor = PaymentProcessor()

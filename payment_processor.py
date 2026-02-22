"""
Payment processing core with Stripe integration and error handling.
"""
import stripe
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, api_key: str):
        self.stripe = stripe
        self.stripe.api_key = api_key
        
    def charge_customer(
        self,
        amount_cents: int,
        currency: str,
        customer_id: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        description: str = ""
    ) -> Tuple[bool, Dict]:
        """
        Process payment with robust error handling.
        Returns (success, response_data)
        """
        try:
            if customer_id and payment_method_id:
                # Create payment intent
                intent = self.stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency.lower(),
                    customer=customer_id,
                    payment_method=payment_method_id,
                    off_session=True,
                    confirm=True,
                    description=description
                )
            else:
                raise ValueError("Missing customer_id or payment_method_id")

            if intent.status == 'succeeded':
                return True, {
                    "id": intent.id,
                    "amount": intent.amount,
                    "currency": intent.currency,
                    "status": intent.status,
                    "created": datetime.fromtimestamp(intent.created)
                }
            
            return False, {
                "error": f"Payment failed with status: {intent.status}",
                "status": intent.status
            }

        except stripe.error.CardError as e:
            logger.error(f"Card error: {e.user_message}")
            return False, {
                "error": str(e.user_message),
                "code": e.code,
                "type": "card_error"
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return False, {
                "error": str(e),
                "type": "stripe_error"
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return False, {
                "error": str(e),
                "type": "unexpected_error"
            }

    def create_customer(self, email: str, name: str = "") -> Dict:
        """Create a new customer record"""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name
            )
            return {
                "id": customer.id,
                "email": customer.email,
                "created": datetime.fromtimestamp(customer.created)
            }
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            raise

    def add_payment_method(
        self,
        customer_id: str,
        payment_method_id: str
    ) -> Dict:
        """Attach payment method to customer"""
        try:
            payment_method = self.stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            return {
                "id": payment_method.id,
                "type": payment_method.type,
                "created": datetime.fromtimestamp(payment_method.created)
            }
        except Exception as e:
            logger.error(f"Failed to add payment method: {str(e)}")
            raise

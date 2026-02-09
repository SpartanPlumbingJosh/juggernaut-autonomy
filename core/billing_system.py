from datetime import datetime, timedelta
from typing import Dict, List, Optional
import stripe
import logging

class BillingSystem:
    """Automated billing and payment processing system."""
    
    def __init__(self, stripe_api_key: str):
        self.stripe = stripe
        self.stripe.api_key = stripe_api_key
        self.logger = logging.getLogger(__name__)
        
    async def create_subscription(self, customer_email: str, plan_id: str) -> Dict:
        """Create a new subscription."""
        try:
            # Create or retrieve customer
            customers = self.stripe.Customer.list(email=customer_email)
            customer = customers.data[0] if customers.data else self.stripe.Customer.create(
                email=customer_email,
                description=f"Autocreated customer for {customer_email}"
            )
            
            # Create subscription
            subscription = self.stripe.Subscription.create(
                customer=customer.id,
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "payment_intent": subscription.latest_invoice.payment_intent
            }
        except Exception as e:
            self.logger.error(f"Subscription creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def process_payment(self, amount: int, currency: str, source: str) -> Dict:
        """Process a direct payment."""
        try:
            payment_intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                payment_method=source,
                confirm=True,
                capture=True
            )
            return {
                "success": True,
                "payment_id": payment_intent.id,
                "status": payment_intent.status
            }
        except Exception as e:
            self.logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def handle_failed_payments(self) -> Dict:
        """Automatically retry failed payments."""
        try:
            failed_payments = self.stripe.PaymentIntent.list(
                status='requires_payment_method',
                created={'gte': int((datetime.now() - timedelta(days=1)).timestamp())}
            )
            
            retried = 0
            for payment in failed_payments.auto_paging_iter():
                try:
                    self.stripe.PaymentIntent.retrieve(payment.id)
                    retried += 1
                except Exception:
                    continue
                    
            return {"success": True, "retried": retried}
        except Exception as e:
            self.logger.error(f"Failed payment handling failed: {str(e)}")
            return {"success": False, "error": str(e)}

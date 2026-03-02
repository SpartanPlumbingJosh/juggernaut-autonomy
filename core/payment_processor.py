import stripe
import logging
from typing import Optional, Dict

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = "your_stripe_secret_key"  # Replace with actual key from env vars
        stripe.api_key = self.stripe_api_key

    async def create_customer(self, email: str, payment_method: str) -> Optional[Dict]:
        try:
            customer = stripe.Customer.create(
                email=email,
                payment_method=payment_method,
                invoice_settings={
                    'default_payment_method': payment_method
                }
            )
            return customer
        except Exception as e:
            logging.error(f"Failed to create customer: {str(e)}")
            return None

    async def create_subscription(self, customer_id: str, price_id: str) -> Optional[Dict]:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return subscription
        except Exception as e:
            logging.error(f"Failed to create subscription: {str(e)}")
            return None

    async def fulfill_order(self, payment_intent_id: str) -> bool:
        """Trigger product/service delivery"""
        try:
            # Implement your fulfillment logic here
            # Example: Grant access, send download link, etc.
            return True
        except Exception as e:
            logging.error(f"Order fulfillment failed: {str(e)}")
            return False

    async def webhook_handler(self, payload: str, sig_header: str) -> bool:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, "your_webhook_signing_secret"
            )
            
            if event['type'] == 'payment_intent.succeeded':
                return await self.fulfill_order(event['data']['object']['id'])
                
            return True
        except Exception as e:
            logging.error(f"Webhook processing failed: {str(e)}")
            return False

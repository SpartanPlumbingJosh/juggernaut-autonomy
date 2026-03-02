import stripe
from datetime import datetime, timezone
from typing import Dict, Optional

stripe.api_key = "sk_test_..."  # Replace with your Stripe secret key

class StripePayment:
    @staticmethod
    async def create_customer(email: str, name: str) -> Optional[str]:
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                description=f"API Marketplace Customer - {datetime.now(timezone.utc).isoformat()}"
            )
            return customer.id
        except Exception as e:
            print(f"Error creating Stripe customer: {str(e)}")
            return None

    @staticmethod
    async def create_subscription(customer_id: str, price_id: str) -> Optional[Dict]:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            print(f"Error creating subscription: {str(e)}")
            return None

    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str, webhook_secret: str) -> Optional[Dict]:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return event
        except Exception as e:
            print(f"Webhook error: {str(e)}")
            return None

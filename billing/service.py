"""
Core billing and payment processing service.
Handles subscription lifecycle and transaction processing.
"""

import datetime
import logging
import stripe
from typing import Dict, Optional

from core.database import query_db
from config import settings

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self):
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    async def create_customer(self, user_id: str, email: str) -> Dict:
        """Create a Stripe customer and save the ID"""
        try:
            customer = stripe.Customer.create(
                email=email,
                metadata={"user_id": user_id}
            )
            
            await query_db(
                f"UPDATE users SET stripe_customer_id = '{customer.id}' WHERE id = '{user_id}'"
            )
            
            return {
                "success": True,
                "customer_id": customer.id
            }
            
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            
            # Record the subscription in our database
            await query_db(
                f"""
                INSERT INTO subscriptions (
                    id, user_id, stripe_subscription_id, 
                    status, price_id, current_period_end,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    (SELECT id FROM users WHERE stripe_customer_id = '{customer_id}'),
                    '{subscription.id}',
                    'incomplete',
                    '{price_id}',
                    to_timestamp({subscription.current_period_end}),
                    NOW()
                )
                """
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
            
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event.type == "invoice.payment_succeeded":
                invoice = event.data.object
                await self._handle_payment_success(invoice)
                
            elif event.type == "invoice.payment_failed":
                invoice = event.data.object  
                await self._handle_payment_failure(invoice)
                
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_payment_success(self, invoice) -> None:
        """Handle successful payment"""
        subscription_id = invoice.subscription
        amount_paid = invoice.amount_paid / 100  # Convert from cents
        
        # Update subscription status
        await query_db(
            f"""
            UPDATE subscriptions 
            SET status = 'active',
                current_period_end = to_timestamp({invoice.period_end})
            WHERE stripe_subscription_id = '{subscription_id}'
            """
        )
        
        # Record revenue event
        user_id = await query_db(
            f"""
            SELECT user_id FROM subscriptions 
            WHERE stripe_subscription_id = '{subscription_id}'
            LIMIT 1
            """
        )
        user_id = user_id.get("rows", [{}])[0].get("user_id")
        
        metadata = {
            "invoice_id": invoice.id,
            "subscription_id": subscription_id
        }
        
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount_paid * 100)},
                '{invoice.currency.upper()}',
                'subscription',
                '{json.dumps(metadata)}',
                NOW()
            )
            """
        )

    async def _handle_payment_failure(self, invoice) -> None:
        """Handle failed payment"""
        subscription_id = invoice.subscription
        
        await query_db(
            f"""
            UPDATE subscriptions 
            SET status = 'past_due'
            WHERE stripe_subscription_id = '{subscription_id}'
            """
        )

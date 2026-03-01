import os
import stripe
from typing import Dict, Any
from datetime import datetime
from core.database import query_db, execute_sql

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class BillingService:
    """Handles all billing operations and webhooks"""
    
    @staticmethod
    async def create_customer(email: str, name: str) -> Dict[str, Any]:
        """Create a new Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"onboarded_at": datetime.utcnow().isoformat()}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def create_subscription(customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a new subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            
            # Record the subscription in our system
            await execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, price_id, status,
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    '{subscription.id}',
                    '{customer_id}',
                    '{price_id}',
                    'pending',
                    {f"to_timestamp({subscription.current_period_start})" if subscription.current_period_start else "NULL"},
                    {f"to_timestamp({subscription.current_period_end})" if subscription.current_period_end else "NULL"},
                    NOW(),
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
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def handle_webhook(payload: Dict[str, Any], sig: str) -> Dict[str, Any]:
        """Process Stripe webhooks"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event.type == 'invoice.paid':
                await BillingService._handle_invoice_paid(event)
            elif event.type == 'invoice.payment_failed':
                await BillingService._handle_payment_failed(event)
            elif event.type == 'customer.subscription.deleted':
                await BillingService._handle_subscription_cancelled(event)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _handle_invoice_paid(event: Any) -> None:
        """Handle successful payment"""
        invoice = event.data.object
        amount_cents = invoice.amount_paid
        
        # Record revenue event
        await execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                '{invoice.currency}',
                'subscription',
                '{json.dumps({"invoice_id": invoice.id, "subscription_id": invoice.subscription})}'::jsonb,
                NOW()
            )
            """
        )
        
        # Update subscription status
        await execute_sql(
            f"""
            UPDATE subscriptions
            SET status = 'active',
                updated_at = NOW()
            WHERE id = '{invoice.subscription}'
            """
        )

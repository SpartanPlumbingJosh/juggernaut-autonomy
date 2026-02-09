from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import stripe
from core.database import query_db, execute_db

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    async def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created on {datetime.utcnow().isoformat()}"
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            event_type = event['type']
            data = event['data']
            
            if event_type == 'invoice.payment_succeeded':
                await self._handle_payment_success(data)
            elif event_type == 'invoice.payment_failed':
                await self._handle_payment_failure(data)
            elif event_type == 'customer.subscription.deleted':
                await self._handle_subscription_cancellation(data)
                
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _handle_payment_success(self, data: Dict[str, Any]) -> None:
        """Handle successful payment."""
        invoice = data['object']
        await execute_db(
            f"""
            INSERT INTO payments (invoice_id, customer_id, amount, currency, status, created_at)
            VALUES ('{invoice['id']}', '{invoice['customer']}', {invoice['amount_paid']}, 
                    '{invoice['currency']}', 'paid', NOW())
            """
        )
        
    async def _handle_payment_failure(self, data: Dict[str, Any]) -> None:
        """Handle failed payment."""
        invoice = data['object']
        await execute_db(
            f"""
            INSERT INTO payments (invoice_id, customer_id, amount, currency, status, created_at)
            VALUES ('{invoice['id']}', '{invoice['customer']}', {invoice['amount_due']}, 
                    '{invoice['currency']}', 'failed', NOW())
            """
        )
        
    async def _handle_subscription_cancellation(self, data: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        subscription = data['object']
        await execute_db(
            f"""
            UPDATE subscriptions
            SET status = 'canceled', canceled_at = NOW()
            WHERE stripe_subscription_id = '{subscription['id']}'
            """
        )

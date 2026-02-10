import stripe
from datetime import datetime, timezone
from typing import Dict, List, Optional
from core.database import query_db

class StripeManager:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        
    async def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer": customer}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        """Create a new subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                expand=["latest_invoice.payment_intent"]
            )
            return {"success": True, "subscription": subscription}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            # Handle specific event types
            if event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_payment_failure(event)
            elif event['type'] == 'customer.subscription.deleted':
                await self._handle_subscription_canceled(event)
                
            return {"success": True}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
            
    async def _handle_payment_success(self, event: Dict) -> None:
        """Record successful payment"""
        invoice = event['data']['object']
        await self._record_revenue_event(
            customer_id=invoice['customer'],
            amount=invoice['amount_paid'],
            currency=invoice['currency'],
            event_type='payment_success',
            invoice_id=invoice['id']
        )
        
    async def _handle_payment_failure(self, event: Dict) -> None:
        """Handle failed payment"""
        invoice = event['data']['object']
        await self._record_revenue_event(
            customer_id=invoice['customer'],
            amount=invoice['amount_due'],
            currency=invoice['currency'],
            event_type='payment_failed',
            invoice_id=invoice['id']
        )
        
    async def _handle_subscription_canceled(self, event: Dict) -> None:
        """Handle subscription cancellation"""
        subscription = event['data']['object']
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'canceled',
                canceled_at = NOW()
            WHERE stripe_subscription_id = '{subscription['id']}'
        """)
        
    async def _record_revenue_event(self, customer_id: str, amount: int, currency: str, 
                                  event_type: str, invoice_id: str) -> None:
        """Record revenue event in database"""
        await query_db(f"""
            INSERT INTO revenue_events (
                id, customer_id, amount_cents, currency,
                event_type, recorded_at, created_at,
                metadata
            ) VALUES (
                gen_random_uuid(),
                '{customer_id}',
                {amount},
                '{currency}',
                '{event_type}',
                NOW(),
                NOW(),
                jsonb_build_object('invoice_id', '{invoice_id}')
            )
        """)

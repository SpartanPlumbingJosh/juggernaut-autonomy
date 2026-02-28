"""
Payment Service - Handles Stripe/PayPal integrations, subscriptions, and billing.
"""
import os
import json
import stripe
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from core.database import query_db
from core.config import get_config

stripe.api_key = get_config("STRIPE_SECRET_KEY")
logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self):
        self.webhook_secret = get_config("STRIPE_WEBHOOK_SECRET")

    async def create_checkout_session(
        self, 
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create Stripe checkout session."""
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {}
            )
            return {"success": True, "session_id": session.id, "url": session.url}
        except Exception as e:
            logger.error(f"Checkout session creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            event_type = event['type']
            data = event['data']['object']
            
            if event_type == 'invoice.paid':
                await self._handle_invoice_paid(data)
            elif event_type == 'invoice.payment_failed':
                await self._handle_payment_failed(data)
            elif event_type == 'customer.subscription.deleted':
                await self._handle_subscription_cancelled(data)
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_invoice_paid(self, invoice: Dict[str, Any]) -> None:
        """Handle successful payment."""
        subscription_id = invoice['subscription']
        customer_id = invoice['customer']
        amount_paid = invoice['amount_paid'] / 100  # Convert to dollars
        
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'active',
                last_payment_at = NOW(),
                next_payment_at = NOW() + INTERVAL '1 month',
                updated_at = NOW()
            WHERE stripe_subscription_id = '{subscription_id}'
        """)
        
        # Record payment in revenue events
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_paid * 100},
                'usd',
                'stripe',
                '{{"subscription_id": "{subscription_id}", "customer_id": "{customer_id}"}}'::jsonb,
                NOW()
            )
        """)

    async def _handle_payment_failed(self, invoice: Dict[str, Any]) -> None:
        """Handle failed payment attempt."""
        subscription_id = invoice['subscription']
        attempts = invoice['attempt_count']
        
        if attempts >= 3:
            # Final failure - cancel subscription
            await query_db(f"""
                UPDATE subscriptions
                SET status = 'past_due',
                    updated_at = NOW()
                WHERE stripe_subscription_id = '{subscription_id}'
            """)
        else:
            # Schedule retry
            await query_db(f"""
                UPDATE subscriptions
                SET status = 'retry_payment',
                updated_at = NOW()
                WHERE stripe_subscription_id = '{subscription_id}'
            """)

    async def _handle_subscription_cancelled(self, subscription: Dict[str, Any]) -> None:
        """Handle subscription cancellation."""
        await query_db(f"""
            UPDATE subscriptions
            SET status = 'canceled',
                canceled_at = NOW(),
                updated_at = NOW()
            WHERE stripe_subscription_id = '{subscription['id']}'
        """)

    async def get_billing_portal_url(self, customer_id: str) -> Dict[str, Any]:
        """Generate Stripe billing portal URL."""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=get_config("BILLING_PORTAL_RETURN_URL")
            )
            return {"success": True, "url": session.url}
        except Exception as e:
            logger.error(f"Billing portal URL generation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_subscription_status(self, subscription_id: str) -> Dict[str, Any]:
        """Check subscription status."""
        try:
            result = await query_db(f"""
                SELECT status, stripe_subscription_id, current_period_end
                FROM subscriptions
                WHERE id = '{subscription_id}'
            """)
            
            if not result.get('rows'):
                return {"success": False, "error": "Subscription not found"}
                
            sub = result['rows'][0]
            return {
                "success": True,
                "status": sub['status'],
                "active": sub['status'] in ['active', 'trialing'],
                "current_period_end": sub['current_period_end']
            }
        except Exception as e:
            logger.error(f"Subscription status check failed: {str(e)}")
            return {"success": False, "error": str(e)}

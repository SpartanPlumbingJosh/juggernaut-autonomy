"""
Payment processing service handling Stripe/PayPal integrations.
"""
import os
import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional

from core.database import query_db

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class PaymentProcessor:
    @staticmethod
    async def create_customer(email: str, name: str) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    'signup_date': datetime.utcnow().isoformat()
                }
            )
            return {'success': True, 'customer_id': customer.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def create_subscription(
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                expand=['latest_invoice.payment_intent'],
                metadata=metadata or {}
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'payment_intent': subscription.latest_invoice.payment_intent
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def handle_webhook(payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
            
            event_type = event['type']
            data = event['data']['object']
            
            # Handle subscription events
            if event_type in [
                'invoice.paid',
                'invoice.payment_failed',
                'customer.subscription.created',
                'customer.subscription.updated',
                'customer.subscription.deleted'
            ]:
                await query_db(f"""
                    INSERT INTO payment_events (
                        event_id, event_type, customer_id, 
                        subscription_id, amount, currency, 
                        invoice_url, status, metadata, 
                        occurred_at, recorded_at
                    ) VALUES (
                        '{event.id}', '{event_type}', 
                        '{data.get('customer')}', 
                        '{data.get('subscription') or data.get('id')}',
                        {data.get('amount_due', 0)},
                        '{data.get('currency', 'usd')}',
                        '{data.get('hosted_invoice_url', '')}',
                        '{data.get('status', '')}',
                        '{json.dumps(data.get('metadata', {}))}'::jsonb,
                        '{datetime.utcfromtimestamp(event.created).isoformat()}',
                        NOW()
                    )
                """)
            
            return {'success': True, 'processed_event': event_type}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

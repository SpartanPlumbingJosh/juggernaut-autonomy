"""
Payment processing integration with Stripe and PayPal.
Handles payment collection, webhooks, and fulfillment.
"""
import os
import json
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.database import query_db
from core.email import send_email

# Initialize payment providers
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET')
})

class PaymentProcessor:
    @staticmethod
    async def create_stripe_checkout(product_data: Dict[str, Any], customer_email: str) -> Dict[str, Any]:
        """Create Stripe checkout session."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': product_data['name'],
                            'description': product_data.get('description', ''),
                        },
                        'unit_amount': int(product_data['price_cents']),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=product_data['success_url'],
                cancel_url=product_data['cancel_url'],
                customer_email=customer_email,
                metadata={
                    'product_id': product_data['id'],
                    'experiment_id': product_data.get('experiment_id', '')
                }
            )
            return {'success': True, 'session_id': session.id, 'url': session.url}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def handle_stripe_webhook(payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                await PaymentProcessor._fulfill_order(
                    payment_provider='stripe',
                    payment_id=session.id,
                    customer_email=session.customer_email,
                    amount_cents=session.amount_total,
                    metadata=session.metadata
                )
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def _fulfill_order(
        payment_provider: str,
        payment_id: str,
        customer_email: str,
        amount_cents: int,
        metadata: Dict[str, Any]
    ) -> None:
        """Handle order fulfillment and database logging."""
        # Record transaction
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount_cents},
                'usd',
                '{payment_provider}',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        # Send confirmation email
        await send_email(
            to_email=customer_email,
            subject="Your Order Confirmation",
            template="order_confirmation",
            context={
                "amount": amount_cents / 100,
                "product_name": metadata.get('product_name', 'your purchase')
            }
        )
        
        # TODO: Trigger product delivery/service fulfillment
        # This would call your specific fulfillment system
        
        # Record customer if new
        await query_db(f"""
            INSERT INTO customers (email, first_purchase_at)
            VALUES ('{customer_email}', NOW())
            ON CONFLICT (email) DO UPDATE SET
                last_purchase_at = NOW(),
                purchase_count = customers.purchase_count + 1
        """)

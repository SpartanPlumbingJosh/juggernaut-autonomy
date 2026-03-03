import os
import stripe
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class PaymentProcessor:
    """Handle payment processing and webhook integration"""
    
    @staticmethod
    async def create_checkout_session(product_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """Create Stripe checkout session"""
        try:
            # Get product details from database
            product = await query_db(f"""
                SELECT id, name, description, price_cents, currency 
                FROM products 
                WHERE id = '{product_id}'
            """)
            product_data = product.get("rows", [{}])[0]
            
            if not product_data:
                return {"error": "Product not found"}
                
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': product_data['currency'],
                        'product_data': {
                            'name': product_data['name'],
                            'description': product_data['description'],
                        },
                        'unit_amount': product_data['price_cents'],
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
            )
            
            return {"session_id": session.id, "url": session.url}
            
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                
                # Record transaction
                await query_db(f"""
                    INSERT INTO revenue_events (
                        id, event_type, amount_cents, currency, 
                        source, metadata, recorded_at, created_at
                    ) VALUES (
                        gen_random_uuid(),
                        'revenue',
                        {session['amount_total']},
                        '{session['currency']}',
                        'stripe',
                        '{json.dumps(session)}'::jsonb,
                        NOW(),
                        NOW()
                    )
                """)
                
                # Trigger product delivery
                await PaymentProcessor.deliver_product(session)
                
            return {"success": True}
            
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def deliver_product(session: Dict[str, Any]) -> bool:
        """Handle product delivery"""
        try:
            # Implement your delivery logic here
            # This could be sending an email, generating a download link, etc.
            return True
        except Exception:
            return False

__all__ = ["PaymentProcessor"]

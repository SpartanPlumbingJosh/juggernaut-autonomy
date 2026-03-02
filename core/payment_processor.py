import os
import stripe
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db
from core.logging import logger

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv('STRIPE_API_KEY')
        stripe.api_key = self.stripe_api_key
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    async def create_checkout_session(self, product_data: Dict, customer_email: str) -> Dict:
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
                        'unit_amount': int(product_data['price'] * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f"{os.getenv('BASE_URL')}/success",
                cancel_url=f"{os.getenv('BASE_URL')}/cancel",
                customer_email=customer_email,
            )
            return {'session_id': session.id, 'url': session.url}
        except Exception as e:
            logger.error(f"Failed to create checkout session: {str(e)}")
            raise

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                await self._fulfill_order(session)
                
            return {'success': True}
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            raise

    async def _fulfill_order(self, session: Dict) -> None:
        try:
            # Record payment in revenue_events
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {session['amount_total']},
                    '{session['currency']}',
                    'stripe',
                    '{json.dumps({
                        'session_id': session['id'],
                        'customer_email': session.get('customer_email'),
                        'payment_intent': session.get('payment_intent')
                    })}',
                    NOW()
                )
                """
            )
            
            # Trigger service fulfillment workflow
            await self._trigger_service_fulfillment(session)
            
        except Exception as e:
            logger.error(f"Failed to fulfill order: {str(e)}")
            raise

    async def _trigger_service_fulfillment(self, session: Dict) -> None:
        # TODO: Implement service-specific fulfillment logic
        pass

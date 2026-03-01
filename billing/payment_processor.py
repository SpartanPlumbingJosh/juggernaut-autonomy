from datetime import datetime
from typing import Dict, Optional
import stripe
from core.database import query_db

class PaymentProcessor:
    def __init__(self, stripe_secret_key: str):
        stripe.api_key = stripe_secret_key
        
    async def create_customer(self, user_id: str, email: str) -> Dict[str, Any]:
        """Create Stripe customer and link to user account"""
        try:
            customer = stripe.Customer.create(
                email=email,
                metadata={'user_id': user_id}
            )
            
            await query_db(
                f"""
                UPDATE users 
                SET stripe_customer_id = '{customer.id}'
                WHERE id = '{user_id}'
                """
            )
            
            return {
                'success': True,
                'customer_id': customer.id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create subscription for customer"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                expand=['latest_invoice.payment_intent']
            )
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'latest_invoice': subscription.latest_invoice.id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                await self._handle_payment_success(event)
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_payment_failure(event)
                
            return {'success': True}
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _handle_payment_success(self, event: Dict[str, Any]) -> None:
        """Handle successful payment"""
        payment_intent = event['data']['object']
        await query_db(
            f"""
            INSERT INTO payments (
                id, user_id, amount, currency, status,
                stripe_payment_intent_id, created_at
            ) VALUES (
                gen_random_uuid(),
                '{payment_intent['metadata']['user_id']}',
                {payment_intent['amount']},
                '{payment_intent['currency']}',
                'succeeded',
                '{payment_intent['id']}',
                NOW()
            )
            """
        )
        
    async def _handle_payment_failure(self, event: Dict[str, Any]) -> None:
        """Handle failed payment"""
        invoice = event['data']['object']
        await query_db(
            f"""
            UPDATE users
            SET payment_status = 'failed'
            WHERE stripe_customer_id = '{invoice['customer']}'
            """
        )

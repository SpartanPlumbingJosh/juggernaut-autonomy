"""
Core Revenue Engine - Handles payment processing, subscriptions, metering and delivery.

Features:
- Stripe/Paddle payment processing
- Subscription lifecycle management 
- Usage metering and billing
- Automated service delivery pipelines
- Payment failure handling and dunning
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import stripe
import paddle

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Payment processor config
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
PADDLE_VENDOR_ID = os.getenv('PADDLE_VENDOR_ID')
PADDLE_API_KEY = os.getenv('PADDLE_API_KEY')

stripe.api_key = STRIPE_API_KEY
paddle_client = paddle.Client(
    vendor_id=int(PADDLE_VENDOR_ID),
    api_key=PADDLE_API_KEY
)

class RevenueEngine:
    """Core revenue processing engine."""
    
    def __init__(self, db_executor):
        self.db = db_executor
        
    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment via Stripe or Paddle."""
        try:
            processor = payment_data.get('processor', 'stripe')
            
            if processor == 'stripe':
                return await self._process_stripe_payment(payment_data)
            elif processor == 'paddle':
                return await self._process_paddle_payment(payment_data)
            else:
                raise ValueError(f"Unsupported payment processor: {processor}")
                
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            raise
            
    async def _process_stripe_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment via Stripe."""
        try:
            # Create Stripe payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(payment_data['amount'] * 100),  # Convert to cents
                currency=payment_data.get('currency', 'usd'),
                payment_method=payment_data['payment_method_id'],
                confirmation_method='manual',
                confirm=True,
                metadata={
                    'user_id': payment_data['user_id'],
                    'product_id': payment_data['product_id']
                }
            )
            
            if intent.status == 'succeeded':
                await self._record_payment(
                    amount=payment_data['amount'],
                    currency=payment_data.get('currency', 'usd'),
                    user_id=payment_data['user_id'],
                    product_id=payment_data['product_id'],
                    processor='stripe',
                    processor_id=intent.id,
                    status='completed'
                )
                return {'status': 'success', 'payment_id': intent.id}
            
            return {'status': 'requires_action', 'client_secret': intent.client_secret}
            
        except stripe.error.CardError as e:
            logger.error(f"Stripe card error: {e.user_message}")
            return {'status': 'failed', 'error': e.user_message}
        except Exception as e:
            logger.error(f"Stripe processing error: {str(e)}")
            raise
            
    async def _process_paddle_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment via Paddle."""
        try:
            # Create Paddle checkout
            response = paddle_client.checkout.create(
                product_id=payment_data['product_id'],
                customer_email=payment_data['email'],
                passthrough=json.dumps({
                    'user_id': payment_data['user_id']
                })
            )
            
            if response.get('success'):
                return {
                    'status': 'requires_action',
                    'checkout_url': response['response']['url']
                }
                
            raise ValueError(f"Paddle checkout failed: {response.get('error')}")
            
        except Exception as e:
            logger.error(f"Paddle processing error: {str(e)}")
            raise
            
    async def _record_payment(self, **kwargs) -> None:
        """Record payment in database."""
        await self.db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                user_id, product_id, processor, processor_id,
                status, recorded_at, metadata
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(kwargs['amount'] * 100)},
                '{kwargs['currency']}',
                '{kwargs['user_id']}',
                '{kwargs['product_id']}',
                '{kwargs['processor']}',
                '{kwargs['processor_id']}',
                '{kwargs['status']}',
                NOW(),
                '{{}}'::jsonb
            )
            """
        )
        
    async def create_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new subscription."""
        try:
            processor = subscription_data.get('processor', 'stripe')
            
            if processor == 'stripe':
                return await self._create_stripe_subscription(subscription_data)
            elif processor == 'paddle':
                return await self._create_paddle_subscription(subscription_data)
            else:
                raise ValueError(f"Unsupported processor: {processor}")
                
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            raise
            
    async def _create_stripe_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe subscription."""
        try:
            # Create customer if needed
            customer_id = subscription_data.get('customer_id')
            if not customer_id:
                customer = stripe.Customer.create(
                    email=subscription_data['email'],
                    payment_method=subscription_data['payment_method_id'],
                    invoice_settings={
                        'default_payment_method': subscription_data['payment_method_id']
                    }
                )
                customer_id = customer.id
                
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{
                    'price': subscription_data['price_id']
                }],
                expand=['latest_invoice.payment_intent'],
                metadata={
                    'user_id': subscription_data['user_id'],
                    'plan_id': subscription_data['plan_id']
                }
            )
            
            # Record subscription
            await self._record_subscription(
                user_id=subscription_data['user_id'],
                plan_id=subscription_data['plan_id'],
                processor='stripe',
                processor_id=subscription.id,
                status=subscription.status
            )
            
            return {
                'status': 'success',
                'subscription_id': subscription.id,
                'customer_id': customer_id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription error: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
            
    async def _create_paddle_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Paddle subscription."""
        try:
            response = paddle_client.subscription.create(
                plan_id=subscription_data['plan_id'],
                customer_email=subscription_data['email'],
                passthrough=json.dumps({
                    'user_id': subscription_data['user_id']
                })
            )
            
            if response.get('success'):
                await self._record_subscription(
                    user_id=subscription_data['user_id'],
                    plan_id=subscription_data['plan_id'],
                    processor='paddle',
                    processor_id=response['response']['subscription_id'],
                    status='active'
                )
                
                return {
                    'status': 'success',
                    'subscription_id': response['response']['subscription_id']
                }
                
            raise ValueError(f"Paddle subscription failed: {response.get('error')}")
            
        except Exception as e:
            logger.error(f"Paddle subscription error: {str(e)}")
            raise
            
    async def _record_subscription(self, **kwargs) -> None:
        """Record subscription in database."""
        await self.db(
            f"""
            INSERT INTO subscriptions (
                id, user_id, plan_id, processor, 
                processor_id, status, created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{kwargs['user_id']}',
                '{kwargs['plan_id']}',
                '{kwargs['processor']}',
                '{kwargs['processor_id']}',
                '{kwargs['status']}',
                NOW(),
                NOW()
            )
            """
        )
        
    async def handle_webhook(self, payload: Dict[str, Any], processor: str) -> Dict[str, Any]:
        """Process payment processor webhook events."""
        try:
            if processor == 'stripe':
                return await self._handle_stripe_webhook(payload)
            elif processor == 'paddle':
                return await self._handle_paddle_webhook(payload)
            else:
                raise ValueError(f"Unsupported processor: {processor}")
                
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            raise
            
    async def _handle_stripe_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        event = stripe.Event.construct_from(payload, stripe.api_key)
        
        if event.type == 'invoice.payment_succeeded':
            await self._handle_stripe_payment_success(event.data.object)
        elif event.type == 'invoice.payment_failed':
            await self._handle_stripe_payment_failure(event.data.object)
        elif event.type == 'customer.subscription.deleted':
            await self._handle_stripe_subscription_canceled(event.data.object)
            
        return {'status': 'processed'}
        
    async def _handle_paddle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Paddle webhook events."""
        if payload['alert_name'] == 'subscription_payment_succeeded':
            await self._handle_paddle_payment_success(payload)
        elif payload['alert_name'] == 'subscription_payment_failed':
            await self._handle_paddle_payment_failure(payload)
        elif payload['alert_name'] == 'subscription_cancelled':
            await self._handle_paddle_subscription_canceled(payload)
            
        return {'status': 'processed'}
        
    async def _handle_stripe_payment_success(self, invoice: Any) -> None:
        """Handle successful Stripe payment."""
        subscription_id = invoice.subscription
        amount = invoice.amount_paid / 100  # Convert to dollars
        
        await self._record_payment(
            amount=amount,
            currency=invoice.currency,
            user_id=invoice.metadata.get('user_id'),
            product_id=invoice.metadata.get('product_id'),
            processor='stripe',
            processor_id=invoice.payment_intent,
            status='completed'
        )
        
        # Update subscription
        await self.db(
            f"""
            UPDATE subscriptions
            SET status = 'active',
                updated_at = NOW()
            WHERE processor_id = '{subscription_id}'
            """
        )
        
    async def _handle_paddle_payment_success(self, payload: Dict[str, Any]) -> None:
        """Handle successful Paddle payment."""
        passthrough = json.loads(payload.get('passthrough', '{}'))
        
        await self._record_payment(
            amount=float(payload['sale_gross']),
            currency=payload['currency'],
            user_id=passthrough.get('user_id'),
            product_id=payload['product_id'],
            processor='paddle',
            processor_id=payload['subscription_id'],
            status='completed'
        )
        
        # Update subscription
        await self.db(
            f"""
            UPDATE subscriptions
            SET status = 'active',
                updated_at = NOW()
            WHERE processor_id = '{payload['subscription_id']}'
            """
        )
        
    async def _handle_stripe_payment_failure(self, invoice: Any) -> None:
        """Handle failed Stripe payment."""
        subscription_id = invoice.subscription
        
        # Record failed payment attempt
        await self._record_payment(
            amount=invoice.amount_due / 100,
            currency=invoice.currency,
            user_id=invoice.metadata.get('user_id'),
            product_id=invoice.metadata.get('product_id'),
            processor='stripe',
            processor_id=invoice.payment_intent,
            status='failed'
        )
        
        # Update subscription status
        await self.db(
            f"""
            UPDATE subscriptions
            SET status = 'past_due',
                updated_at = NOW()
            WHERE processor_id = '{subscription_id}'
            """
        )
        
        # Trigger dunning process
        await self._trigger_dunning_process(
            user_id=invoice.metadata.get('user_id'),
            subscription_id=subscription_id,
            failure_reason=invoice.attempt_count
        )
        
    async def _handle_paddle_payment_failure(self, payload: Dict[str, Any]) -> None:
        """Handle failed Paddle payment."""
        passthrough = json.loads(payload.get('passthrough', '{}'))
        
        # Record failed payment
        await self._record_payment(
            amount=float(payload['sale_gross']),
            currency=payload['currency'],
            user_id=passthrough.get('user_id'),
            product_id=payload['product_id'],
            processor='paddle',
            processor_id=payload['subscription_id'],
            status='failed'
        )
        
        # Update subscription status
        await self.db(
            f"""
            UPDATE subscriptions
            SET status = 'past_due',
                updated_at = NOW()
            WHERE processor_id = '{payload['subscription_id']}'
            """
        )
        
        # Trigger dunning process
        await self._trigger_dunning_process(
            user_id=passthrough.get('user_id'),
            subscription_id=payload['subscription_id'],
            failure_reason=payload.get('error_message')
        )
        
    async def _trigger_dunning_process(self, **kwargs) -> None:
        """Handle payment failure recovery process."""
        # Get subscription details
        sub = await self.db(
            f"""
            SELECT * FROM subscriptions
            WHERE processor_id = '{kwargs['subscription_id']}'
            LIMIT 1
            """
        )
        sub = sub.get('rows', [{}])[0]
        
        # Get user details
        user = await self.db(
            f"""
            SELECT email FROM users
            WHERE id = '{kwargs['user_id']}'
            LIMIT 1
            """
        )
        user = user.get('rows', [{}])[0]
        
        # Record dunning attempt
        await self.db(
            f"""
            INSERT INTO dunning_attempts (
                id, subscription_id, user_id, 
                attempt_number, failure_reason, created_at
            ) VALUES (
                gen_random_uuid(),
                '{sub['id']}',
                '{kwargs['user_id']}',
                COALESCE((SELECT MAX(attempt_number) FROM dunning_attempts WHERE subscription_id = '{sub['id']}'), 0) + 1,
                '{kwargs['failure_reason']}',
                NOW()
            )
            """
        )
        
        # TODO: Implement actual dunning flow (email notifications, retry logic, etc)
        logger.info(f"Dunning process triggered for user {kwargs['user_id']}")
        
    async def meter_usage(self, usage_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record usage for metered billing."""
        try:
            await self.db(
                f"""
                INSERT INTO usage_records (
                    id, user_id, subscription_id, 
                    metric_id, quantity, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    '{usage_data['user_id']}',
                    '{usage_data['subscription_id']}',
                    '{usage_data['metric_id']}',
                    {usage_data['quantity']},
                    NOW()
                )
                """
            )
            
            return {'status': 'success'}
            
        except Exception as e:
            logger.error(f"Usage metering failed: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
            
    async def process_deliverables(self, delivery_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process service/product delivery after successful payment."""
        try:
            # TODO: Implement actual delivery pipeline based on product type
            logger.info(f"Processing delivery for {delivery_data}")
            
            # Mark as delivered
            await self.db(
                f"""
                UPDATE revenue_events
                SET metadata = jsonb_set(
                    COALESCE(metadata, '{{}}'::jsonb),
                    '{{delivered}}',
                    'true'
                )
                WHERE processor_id = '{delivery_data['payment_id']}'
                """
            )
            
            return {'status': 'success'}
            
        except Exception as e:
            logger.error(f"Delivery processing failed: {str(e)}")
            return {'status': 'failed', 'error': str(e)}

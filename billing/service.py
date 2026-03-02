"""
Autonomous billing service supporting subscriptions, usage billing and one-time payments.
Integrates with Stripe and Paddle payment processors via webhooks.
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import stripe
from tenacity import retry, stop_after_attempt, wait_exponential

from core.database import query_db
from core.logging import get_logger

logger = get_logger(__name__)

# Payment processor configurations
PROCESSORS = {
    'stripe': {
        'api_key': None,
        'webhook_secret': None,
        'retry_attempts': 3
    },
    'paddle': {
        'api_key': None,
        'webhook_secret': None,
        'retry_attempts': 3
    }
}

class BillingService:
    def __init__(self):
        self.configure_processors()

    def configure_processors(self):
        """Load processor configs from environment/database"""
        try:
            # TODO: Load actual config from secure storage
            PROCESSORS['stripe']['api_key'] = 'sk_test_...'
            PROCESSORS['stripe']['webhook_secret'] = 'whsec_...'
            PROCESSORS['paddle']['api_key'] = 'paddle_...'
            PROCESSORS['paddle']['webhook_secret'] = 'paddle_whsec_...'
            
            stripe.api_key = PROCESSORS['stripe']['api_key']
        except Exception as e:
            logger.error(f"Failed to configure payment processors: {str(e)}")

    async def record_transaction(
        self,
        amount_cents: int,
        currency: str = 'usd',
        event_type: str = 'revenue',
        source: str = 'stripe',
        metadata: Optional[Dict] = None,
        recorded_at: Optional[datetime] = None
    ) -> bool:
        """Record a financial transaction in database"""
        recorded_at = recorded_at or datetime.now(timezone.utc)
        try:
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata or {})}',
                    '{recorded_at.isoformat()}',
                    NOW()
                )
                """
            )
            return True
        except Exception as e:
            logger.error(f"Failed to record transaction: {str(e)}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def charge_customer(
        self,
        processor: str,
        amount_cents: int,
        customer_id: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """Charge a customer with retry logic"""
        try:
            if processor == 'stripe':
                charge = stripe.Charge.create(
                    amount=amount_cents,
                    currency='usd',
                    customer=customer_id,
                    description=description,
                    metadata=metadata or {}
                )
                return True, charge
            elif processor == 'paddle':
                # Paddle implementation would go here
                pass
            return False, None
        except Exception as e:
            logger.warning(f"Payment attempt failed: {str(e)}")
            raise

    async def handle_webhook(self, processor: str, payload: Dict, signature: str) -> bool:
        """Process payment processor webhook events"""
        try:
            if processor == 'stripe':
                event = stripe.Webhook.construct_event(
                    json.dumps(payload),
                    signature,
                    PROCESSORS['stripe']['webhook_secret']
                )
                
                if event['type'] == 'payment_intent.succeeded':
                    payment = event['data']['object']
                    await self.record_transaction(
                        amount_cents=payment['amount'],
                        currency=payment['currency'],
                        source='stripe',
                        metadata={
                            'payment_id': payment['id'],
                            'customer': payment['customer'],
                            'payment_intent': payment.get('payment_intent')
                        }
                    )
                # Handle other event types...
                
            return True
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False

    async def create_invoice(self, subscription_id: str) -> Optional[Dict]:
        """Generate invoice for subscription"""
        try:
            # TODO: Implement proper invoice generation
            return {
                'id': 'inv_...',
                'status': 'draft',
                'subscription_id': subscription_id,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Invoice creation failed: {str(e)}")
            return None

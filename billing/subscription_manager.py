import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from enum import Enum, auto

from billing.payment_processors import StripePaymentProcessor
from core.database import query_db

logger = logging.getLogger(__name__)

class PaymentStatus(Enum):
    SUCCEEDED = auto()
    FAILED = auto()
    PENDING = auto()
    REFUNDED = auto()

class SubscriptionStatus(Enum):
    ACTIVE = auto()
    CANCELED = auto()
    PAST_DUE = auto()
    UNPAID = auto()
    TRIALING = auto()

class SubscriptionManager:
    """Handles all subscription lifecycle operations"""
    
    def __init__(self):
        self.processor = StripePaymentProcessor()
        self.processor.connect()
        
    async def create_subscription(self, customer_id: str, plan_id: str, 
                                 billing_details: Dict) -> Tuple[bool, Optional[Dict]]:
        """Create new subscription"""
        try:
            # Create payment method
            pm_id = self.processor.create_payment_method(
                customer_id,
                billing_details['payment_method']
            )
            if not pm_id:
                return False, {'error': 'Failed to create payment method'}
                
            # Create subscription
            sub_id = self.processor.create_subscription(
                customer_id,
                plan_id,
                pm_id
            )
            if not sub_id:
                return False, {'error': 'Failed to create subscription'}
                
            # Record in DB
            await query_db(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    payment_method_id, created_at, updated_at
                ) VALUES (
                    '{sub_id}', '{customer_id}', '{plan_id}', 
                    '{SubscriptionStatus.TRIALING.name}',
                    '{pm_id}', NOW(), NOW()
                )
                """
            )
            
            return True, {'subscription_id': sub_id}
            
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            return False, {'error': str(e)}
            
    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription"""
        try:
            # Cancel in Stripe
            self.processor.client.Subscription.delete(subscription_id)
            
            # Update DB
            await query_db(
                f"""
                UPDATE subscriptions 
                SET status = '{SubscriptionStatus.CANCELED.name}',
                    updated_at = NOW(),
                    canceled_at = NOW()
                WHERE id = '{subscription_id}'
                """
            )
            return True
        except Exception as e:
            logger.error(f"Subscription cancellation failed: {str(e)}")
            return False
            
    async def process_upcoming_invoices(self):
        """Process upcoming invoices (run daily via cron)"""
        logger.info("Processing upcoming invoices...")
        
        # Get subscriptions with upcoming renewal
        result = await query_db(f"""
            SELECT id, customer_id 
            FROM subscriptions
            WHERE status = '{SubscriptionStatus.ACTIVE.name}'
            AND next_billing_date <= NOW() + INTERVAL '7 days'
        """)
        
        subscribed = result.get('rows', [])
        for sub in subscribed:
            sub_id = sub.get('id')
            customer_id = sub.get('customer_id')
            
            try:
                # Get upcoming invoice from Stripe
                invoices = self.processor.client.Invoice.upcoming(
                    customer=customer_id,
                    subscription=sub_id
                )
                
                # Process payment
                payment_success, _ = self.processor.charge(
                    customer_id,
                    invoices['amount_due'],
                    invoices['currency'],
                    f"Invoice for subscription {sub_id}"
                )
                
                if payment_success:
                    # Update DB
                    await query_db(f"""
                        UPDATE subscriptions
                        SET last_payment_date = NOW(),
                            next_billing_date = NOW() + INTERVAL '1 month',
                            updated_at = NOW()
                        WHERE id = '{sub_id}'
                    """)
                    
                    # Record revenue event
                    await query_db(f"""
                        INSERT INTO revenue_events (
                            event_type, amount_cents, currency,
                            customer_id, subscription_id,
                            recorded_at, created_at
                        ) VALUES (
                            'revenue', {invoices['amount_due']}, '{invoices['currency']}',
                            '{customer_id}', '{sub_id}',
                            NOW(), NOW()
                        )
                    """)
                else:
                    # Trigger payment failure workflow
                    await self.handle_payment_failure(sub_id)
                    
            except Exception as e:
                logger.error(f"Failed to process invoice for sub {sub_id}: {str(e)}")
                await self.handle_payment_failure(sub_id)
                
    async def handle_payment_failure(self, subscription_id: str) -> bool:
        """Handle failed subscription payment (dunning)"""
        # Implement dunning workflow:
        # 1. Update subscription status
        # 2. Send notification to customer
        # 3. Schedule retry attempts
        # 4. Eventually cancel if all attempts fail
        pass

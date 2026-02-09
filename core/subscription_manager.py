from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

class SubscriptionManager:
    """Manages subscriptions and recurring billing."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.logger = logging.getLogger(__name__)
        
    def create_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Log subscription creation
            self.log_action(
                "subscription.created",
                "New subscription created",
                level="info",
                output_data=subscription_data
            )
            
            # Create subscription record
            self.execute_sql(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    start_date, end_date, created_at,
                    updated_at, metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{subscription_data.get('customer_id')}',
                    '{subscription_data.get('plan_id')}',
                    'active',
                    NOW(),
                    NOW() + INTERVAL '1 year',
                    NOW(),
                    NOW(),
                    '{json.dumps(subscription_data)}'::jsonb
                )
            """)
            
            return {
                "success": True,
                "subscription_id": subscription_data.get('customer_id'),
                "status": "active"
            }
            
        except Exception as e:
            self.logger.error(f"Subscription creation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def process_recurring_billing(self) -> Dict[str, Any]:
        """Process recurring billing for active subscriptions."""
        try:
            # Get subscriptions due for billing
            res = self.execute_sql("""
                SELECT id, customer_id, plan_id, metadata
                FROM subscriptions
                WHERE status = 'active'
                  AND end_date <= NOW() + INTERVAL '7 days'
                ORDER BY end_date ASC
                LIMIT 100
            """)
            subscriptions = res.get("rows", [])
            
            billed = 0
            for sub in subscriptions:
                # Process payment
                payment_data = {
                    "amount": sub.get('metadata', {}).get('amount', 0),
                    "currency": sub.get('metadata', {}).get('currency', 'USD'),
                    "subscription_id": sub.get('id')
                }
                
                # Record transaction
                self.execute_sql(f"""
                    INSERT INTO revenue_events (
                        id, event_type, amount_cents, currency,
                        source, metadata, recorded_at, created_at
                    ) VALUES (
                        gen_random_uuid(),
                        'revenue',
                        {int(float(payment_data.get('amount', 0)) * 100)},
                        '{payment_data.get('currency', 'USD')}',
                        'subscription',
                        '{json.dumps(payment_data)}'::jsonb,
                        NOW(),
                        NOW()
                    )
                """)
                
                # Update subscription
                self.execute_sql(f"""
                    UPDATE subscriptions
                    SET end_date = end_date + INTERVAL '1 month',
                        updated_at = NOW()
                    WHERE id = '{sub.get('id')}'
                """)
                
                billed += 1
                
            return {
                "success": True,
                "subscriptions_billed": billed
            }
            
        except Exception as e:
            self.logger.error(f"Recurring billing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

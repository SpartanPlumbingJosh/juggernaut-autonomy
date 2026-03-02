from datetime import datetime, timedelta
from typing import Dict, Optional
from core.database import query_db

class SubscriptionManager:
    """Handles subscription lifecycle management."""
    
    def __init__(self, payment_processor: str = 'stripe'):
        self.processor = get_payment_processor(payment_processor)
        
    def create_subscription(self, user_id: str, plan_id: str, payment_method: Dict) -> Dict:
        """Create new subscription for user."""
        # Get user email from DB
        user = query_db(f"SELECT email FROM users WHERE id = '{user_id}'").get('rows', [{}])[0]
        email = user.get('email')
        
        if not email:
            raise ValueError("User email not found")
            
        # Create customer in payment processor
        customer_id = self.processor.create_customer(email, payment_method)
        
        # Create subscription
        subscription_id = self.processor.create_subscription(customer_id, plan_id)
        
        # Store in database
        now = datetime.utcnow()
        billing_cycle_start = now
        billing_cycle_end = now + timedelta(days=30)  # Monthly by default
        
        query_db(f"""
            INSERT INTO subscriptions (
                id, user_id, plan_id, 
                customer_id, subscription_id,
                status, billing_cycle_start,
                billing_cycle_end, created_at
            ) VALUES (
                gen_random_uuid(), '{user_id}', '{plan_id}',
                '{customer_id}', '{subscription_id}',
                'active', '{billing_cycle_start.isoformat()}',
                '{billing_cycle_end.isoformat()}', NOW()
            )
        """)
        
        return {
            'customer_id': customer_id,
            'subscription_id': subscription_id,
            'billing_cycle_start': billing_cycle_start,
            'billing_cycle_end': billing_cycle_end
        }
    
    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel an existing subscription."""
        # TODO: Implement cancelation logic
        pass
    
    def get_active_subscriptions(self, user_id: str) -> Dict:
        """Get all active subscriptions for user."""
        result = query_db(f"""
            SELECT * FROM subscriptions 
            WHERE user_id = '{user_id}' AND status = 'active'
        """)
        return result.get('rows', [])

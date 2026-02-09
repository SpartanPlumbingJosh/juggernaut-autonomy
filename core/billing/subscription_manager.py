"""
Automated subscription lifecycle management.
Features:
- Automated billing cycles
- Dunning management
- Usage-based billing
- Self-healing capabilities
"""

import datetime
from typing import Dict, List

from core.database import query_db, execute_db


class SubscriptionManager:
    """Manage subscription billing cycles and service delivery."""
    
    async def run_billing_cycle(self):
        """Execute automated billing cycle."""
        # Get all active subscriptions due for billing
        subscriptions = await query_db(
            """
            SELECT s.id, s.customer_id, s.billing_cycle, s.next_billing_date, 
                   s.metadata, p.payment_method_id
            FROM subscriptions s
            JOIN customer_payment_methods p ON s.customer_id = p.customer_id
            WHERE s.status = 'active'
              AND s.next_billing_date <= NOW()
              AND p.is_default = TRUE
            """
        )
        
        processed = 0
        for sub in subscriptions.get('rows', []):
            try:
                await self._process_subscription_billing(sub)
                processed += 1
            except Exception as e:
                await self._handle_billing_failure(sub, str(e))
                
        return {'success': True, 'processed': processed}
    
    async def _process_subscription_billing(self, subscription: Dict):
        """Process single subscription billing."""
        sub_id = subscription['id']
        
        # Calculate amount (could include usage-based calculations)
        amount_cents = await self._calculate_billing_amount(sub_id)
        
        # Process payment
        payment_result = await payment_orchestrator.process_payment(
            amount_cents=amount_cents,
            customer_id=subscription['customer_id'],
            provider='stripe',  # Would be configurable
            metadata={
                'subscription_id': sub_id,
                'billing_cycle': subscription['billing_cycle']
            }
        )
        
        # Record successful payment
        await execute_db(
            """
            INSERT INTO subscription_payments 
            (subscription_id, amount_cents, payment_result, occurred_at)
            VALUES (%s, %s, %s, NOW())
            """,
            [sub_id, amount_cents, json.dumps(payment_result)]
        )
        
        # Update next billing date
        next_date = self._calculate_next_billing_date(
            datetime.date.today(),
            subscription['billing_cycle']
        )
        
        await execute_db(
            """
            UPDATE subscriptions
            SET last_billed_at = NOW(),
                next_billing_date = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            [next_date, sub_id]
        )
        
    async def _calculate_billing_amount(self, subscription_id: str) -> int:
        """Calculate billing amount including any usage charges."""
        # Base price
        result = await query_db(
            "SELECT base_price_cents FROM subscriptions WHERE id = %s",
            [subscription_id]
        )
        amount = result['rows'][0]['base_price_cents']
        
        # Add usage charges if any
        usage_result = await query_db(
            """
            SELECT SUM(units * rate_cents) as usage_amount
            FROM subscription_usage
            WHERE subscription_id = %s
              AND billing_status = 'pending'
            """,
            [subscription_id]
        )
        
        if usage_result['rows'][0]['usage_amount']:
            amount += usage_result['rows'][0]['usage_amount']
            await execute_db(
                "UPDATE subscription_usage SET billing_status = 'billed' WHERE subscription_id = %s",
                [subscription_id]
            )
            
        return amount
        
    def _calculate_next_billing_date(self, current_date: datetime.date, cycle: str) -> datetime.date:
        """Calculate next billing date based on cycle."""
        if cycle == 'monthly':
            return current_date + datetime.timedelta(days=30)
        elif cycle == 'quarterly':
            return current_date + datetime.timedelta(days=90)
        elif cycle == 'annual': 
            return current_date + datetime.timedelta(days=365)
        else:
            return current_date + datetime.timedelta(days=30)  # Default to monthly
            
    async def _handle_billing_failure(self, subscription: Dict, error: str):
        """Handle billing failure with dunning process."""
        sub_id = subscription['id']
        
        # Record failure
        await execute_db(
            """
            INSERT INTO subscription_billing_failures 
            (subscription_id, amount_attempted, error_message, occurred_at)
            VALUES (%s, %s, %s, NOW())
            """,
            [sub_id, subscription['base_price_cents'], error]
        )
        
        # Implement dunning process logic here
        # Example: retry logic, notify ops team, downgrade customer, etc.

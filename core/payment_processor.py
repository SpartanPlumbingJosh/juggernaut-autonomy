"""
Core payment processing system - handles subscriptions, invoices, and revenue recognition.
Integrates with payment providers and manages failed payments, renewals, and upgrades.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.database import query_db, execute_db

# Payment provider integrations
class PaymentProvider:
    """Base class for payment provider integrations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def create_customer(self, email: str, name: str) -> Tuple[str, Optional[str]]:
        """Create a new customer in the payment provider."""
        raise NotImplementedError
        
    def create_subscription(self, customer_id: str, plan_id: str) -> Tuple[str, Optional[str]]:
        """Create a new subscription."""
        raise NotImplementedError
        
    def update_subscription(self, subscription_id: str, new_plan_id: str) -> bool:
        """Update an existing subscription."""
        raise NotImplementedError
        
    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription."""
        raise NotImplementedError
        
    def create_invoice(self, customer_id: str, amount: float, currency: str) -> Tuple[str, Optional[str]]:
        """Create an invoice."""
        raise NotImplementedError
        
    def process_payment(self, payment_method_id: str, amount: float, currency: str) -> Tuple[bool, Optional[str]]:
        """Process a payment."""
        raise NotImplementedError
        
    def handle_webhook(self, payload: Dict[str, Any]) -> bool:
        """Handle webhook events from the provider."""
        raise NotImplementedError


class StripeProvider(PaymentProvider):
    """Stripe payment provider implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import stripe
        stripe.api_key = config['api_key']
        self.stripe = stripe
        
    def create_customer(self, email: str, name: str) -> Tuple[str, Optional[str]]:
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name
            )
            return customer.id, None
        except Exception as e:
            return None, str(e)
    
    # Implement other Stripe methods...


class PaymentProcessor:
    """Core payment processing system."""
    
    def __init__(self, provider: PaymentProvider):
        self.provider = provider
        self.logger = logging.getLogger(__name__)
        
    async def create_subscription(self, user_id: str, plan_id: str, payment_method: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new subscription for a user."""
        try:
            # Get user details
            user = await query_db(f"SELECT * FROM users WHERE id = '{user_id}'")
            if not user.get('rows'):
                return {"success": False, "error": "User not found"}
            
            user_data = user['rows'][0]
            
            # Create customer in payment provider
            customer_id, error = self.provider.create_customer(
                email=user_data['email'],
                name=user_data['name']
            )
            if error:
                return {"success": False, "error": error}
            
            # Create subscription
            subscription_id, error = self.provider.create_subscription(
                customer_id=customer_id,
                plan_id=plan_id
            )
            if error:
                return {"success": False, "error": error}
            
            # Store subscription in database
            await execute_db(f"""
                INSERT INTO subscriptions (
                    id, user_id, plan_id, status, 
                    customer_id, subscription_id,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{user_id}',
                    '{plan_id}',
                    'active',
                    '{customer_id}',
                    '{subscription_id}',
                    NOW(),
                    NOW()
                )
            """)
            
            return {"success": True, "subscription_id": subscription_id}
            
        except Exception as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def handle_payment_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment webhook events."""
        try:
            if not self.provider.handle_webhook(payload):
                return {"success": False, "error": "Webhook handling failed"}
            
            event_type = payload.get('type')
            if event_type == 'payment_failed':
                await self.handle_failed_payment(payload)
            elif event_type == 'subscription_updated':
                await self.handle_subscription_update(payload)
            elif event_type == 'invoice_paid':
                await self.handle_invoice_payment(payload)
            
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to handle webhook: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def handle_failed_payment(self, payload: Dict[str, Any]) -> None:
        """Handle failed payment events."""
        subscription_id = payload.get('data', {}).get('object', {}).get('subscription')
        if not subscription_id:
            return
            
        await execute_db(f"""
            UPDATE subscriptions
            SET status = 'payment_failed',
                updated_at = NOW()
            WHERE subscription_id = '{subscription_id}'
        """)
        
        # Notify user and retry logic would go here
    
    async def handle_subscription_update(self, payload: Dict[str, Any]) -> None:
        """Handle subscription update events."""
        subscription_id = payload.get('data', {}).get('object', {}).get('id')
        if not subscription_id:
            return
            
        new_plan_id = payload.get('data', {}).get('object', {}).get('plan', {}).get('id')
        if not new_plan_id:
            return
            
        await execute_db(f"""
            UPDATE subscriptions
            SET plan_id = '{new_plan_id}',
                updated_at = NOW()
            WHERE subscription_id = '{subscription_id}'
        """)
    
    async def handle_invoice_payment(self, payload: Dict[str, Any]) -> None:
        """Handle invoice payment events."""
        invoice = payload.get('data', {}).get('object', {})
        if not invoice:
            return
            
        amount = invoice.get('amount_paid')
        currency = invoice.get('currency')
        customer_id = invoice.get('customer')
        
        if not all([amount, currency, customer_id]):
            return
            
        # Record revenue event
        await execute_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {int(amount)},
                '{currency}',
                'subscription',
                '{json.dumps({'invoice_id': invoice.get('id')})}',
                NOW(),
                NOW()
            )
        """)

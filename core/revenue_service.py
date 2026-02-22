import os
import stripe
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.database import query_db, execute_db

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class RevenueService:
    """Core service for handling revenue operations and subscriptions."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def create_customer(self, email: str, name: str) -> Dict[str, Any]:
        """Create a new customer in Stripe and our system."""
        try:
            # Create Stripe customer
            customer = stripe.Customer.create(
                email=email,
                name=name,
                description=f"Customer created {datetime.now(timezone.utc).isoformat()}"
            )
            
            # Store in our database
            await execute_db(
                f"""
                INSERT INTO customers (stripe_id, email, name, created_at)
                VALUES ('{customer.id}', '{email}', '{name}', NOW())
                """
            )
            
            return {"success": True, "customer_id": customer.id}
            
        except Exception as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a subscription for a customer."""
        try:
            # Create Stripe subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            
            # Store in our database
            await execute_db(
                f"""
                INSERT INTO subscriptions (stripe_id, customer_id, status, created_at)
                VALUES ('{subscription.id}', '{customer_id}', 'pending', NOW())
                """
            )
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def recover_failed_payments(self) -> Dict[str, Any]:
        """Attempt to recover failed payments."""
        try:
            # Get failed payments
            res = await query_db(
                """
                SELECT stripe_id, customer_id, amount, currency
                FROM payments
                WHERE status = 'failed'
                AND created_at > NOW() - INTERVAL '7 days'
                """
            )
            failed_payments = res.get("rows", [])
            
            recovered = 0
            for payment in failed_payments:
                try:
                    # Attempt to retry payment
                    stripe.PaymentIntent.create(
                        amount=payment['amount'],
                        currency=payment['currency'],
                        customer=payment['customer_id'],
                        payment_method='card',
                        confirm=True
                    )
                    
                    # Update status
                    await execute_db(
                        f"""
                        UPDATE payments
                        SET status = 'recovered',
                            updated_at = NOW()
                        WHERE stripe_id = '{payment['stripe_id']}'
                        """
                    )
                    recovered += 1
                    
                except Exception:
                    continue
                    
            return {"success": True, "recovered": recovered, "total": len(failed_payments)}
            
        except Exception as e:
            self.logger.error(f"Payment recovery failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
            
            # Handle different event types
            if event['type'] == 'customer.subscription.created':
                await self._handle_subscription_created(event['data']['object'])
            elif event['type'] == 'customer.subscription.updated':
                await self._handle_subscription_updated(event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_succeeded(event['data']['object'])
                
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _handle_subscription_created(self, subscription: Dict[str, Any]) -> None:
        """Handle new subscription creation."""
        await execute_db(
            f"""
            UPDATE subscriptions
            SET status = 'active',
                current_period_start = to_timestamp({subscription['current_period_start']}),
                current_period_end = to_timestamp({subscription['current_period_end']})
            WHERE stripe_id = '{subscription['id']}'
            """
        )
        
    async def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> None:
        """Handle subscription updates."""
        await execute_db(
            f"""
            UPDATE subscriptions
            SET status = '{subscription['status']}',
                current_period_start = to_timestamp({subscription['current_period_start']}),
                current_period_end = to_timestamp({subscription['current_period_end']})
            WHERE stripe_id = '{subscription['id']}'
            """
        )
        
    async def _handle_payment_succeeded(self, invoice: Dict[str, Any]) -> None:
        """Handle successful payments."""
        await execute_db(
            f"""
            INSERT INTO payments (
                stripe_id, customer_id, amount, currency, status, created_at
            ) VALUES (
                '{invoice['id']}', '{invoice['customer']}', {invoice['amount_paid']},
                '{invoice['currency']}', 'succeeded', NOW()
            )
            """
        )

from typing import Dict, Optional
from datetime import datetime
from core.payment_processor import PaymentProcessor
from core.database import query_db

class PaymentWebhooks:
    def __init__(self, processor: PaymentProcessor):
        self.processor = processor
        
    async def handle_invoice_payment_succeeded(self, event: Dict) -> None:
        """Handle successful invoice payment."""
        invoice = event["data"]["object"]
        customer_id = invoice["customer"]
        amount_paid = invoice["amount_paid"] / 100  # Convert to dollars
        currency = invoice["currency"].upper()
        
        # Record payment in database
        await query_db(
            f"""
            INSERT INTO payments (customer_id, amount, currency, status, payment_date)
            VALUES ('{customer_id}', {amount_paid}, '{currency}', 'successful', NOW())
            """
        )
        
    async def handle_invoice_payment_failed(self, event: Dict) -> None:
        """Handle failed invoice payment."""
        invoice = event["data"]["object"]
        customer_id = invoice["customer"]
        amount = invoice["amount_due"] / 100
        currency = invoice["currency"].upper()
        
        # Record failed payment attempt
        await query_db(
            f"""
            INSERT INTO payments (customer_id, amount, currency, status, payment_date)
            VALUES ('{customer_id}', {amount}, '{currency}', 'failed', NOW())
            """
        )
        
    async def handle_subscription_created(self, event: Dict) -> None:
        """Handle new subscription creation."""
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]
        subscription_id = subscription["id"]
        start_date = datetime.fromtimestamp(subscription["current_period_start"])
        end_date = datetime.fromtimestamp(subscription["current_period_end"])
        
        # Record subscription in database
        await query_db(
            f"""
            INSERT INTO subscriptions (customer_id, subscription_id, start_date, end_date, status)
            VALUES ('{customer_id}', '{subscription_id}', '{start_date}', '{end_date}', 'active')
            """
        )
        
    async def handle_subscription_updated(self, event: Dict) -> None:
        """Handle subscription changes."""
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        status = subscription["status"]
        
        # Update subscription status
        await query_db(
            f"""
            UPDATE subscriptions
            SET status = '{status}'
            WHERE subscription_id = '{subscription_id}'
            """
        )
        
    async def handle_subscription_deleted(self, event: Dict) -> None:
        """Handle subscription cancellation."""
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        
        # Mark subscription as canceled
        await query_db(
            f"""
            UPDATE subscriptions
            SET status = 'canceled'
            WHERE subscription_id = '{subscription_id}'
            """
        )
        
    async def handle_payment_method_attached(self, event: Dict) -> None:
        """Handle new payment method being added."""
        payment_method = event["data"]["object"]
        customer_id = payment_method["customer"]
        payment_method_id = payment_method["id"]
        
        # Record payment method in database
        await query_db(
            f"""
            INSERT INTO payment_methods (customer_id, payment_method_id, type, status)
            VALUES ('{customer_id}', '{payment_method_id}', 'card', 'active')
            """
        )
        
    async def handle_payment_method_detached(self, event: Dict) -> None:
        """Handle payment method removal."""
        payment_method = event["data"]["object"]
        payment_method_id = payment_method["id"]
        
        # Mark payment method as removed
        await query_db(
            f"""
            UPDATE payment_methods
            SET status = 'removed'
            WHERE payment_method_id = '{payment_method_id}'
            """
        )

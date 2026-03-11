"""
Payment Processor Service - Handles subscriptions, usage-based billing, invoices, and fraud detection.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
import uuid

import stripe
from taxjar.client import TaxJarClient
from fraud_detection import FraudDetector

# Initialize services
stripe.api_key = "sk_test_..."  # Should be from environment
taxjar_client = TaxJarClient(api_key="taxjar_api_key")  # From environment
fraud_detector = FraudDetector()

class PaymentProcessor:
    """Core payment processing functionality."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        self.logger = logging.getLogger(__name__)
        
    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Create Stripe subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                default_payment_method=payment_method,
                expand=["latest_invoice.payment_intent"]
            )
            
            # Store in database
            await self.execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    '{subscription.id}', '{customer_id}', '{plan_id}', 'active',
                    '{datetime.fromtimestamp(subscription.current_period_start).isoformat()}',
                    '{datetime.fromtimestamp(subscription.current_period_end).isoformat()}',
                    NOW(), NOW()
                )
                """
            )
            
            return {"success": True, "subscription": subscription}
        except Exception as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def process_usage_billing(self, subscription_id: str, usage_units: int) -> Dict[str, Any]:
        """Process usage-based billing for a subscription."""
        try:
            # Record usage with Stripe
            stripe.SubscriptionItem.create_usage_record(
                subscription_id,
                quantity=usage_units,
                timestamp=int(datetime.now().timestamp())
            )
            
            # Update database
            await self.execute_sql(
                f"""
                UPDATE subscriptions
                SET usage_units = usage_units + {usage_units},
                    updated_at = NOW()
                WHERE id = '{subscription_id}'
                """
            )
            
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to process usage billing: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def generate_invoice(self, subscription_id: str) -> Dict[str, Any]:
        """Generate and finalize an invoice."""
        try:
            # Create invoice in Stripe
            invoice = stripe.Invoice.create(
                subscription=subscription_id,
                auto_advance=True
            )
            
            # Calculate taxes
            tax_data = taxjar_client.calculate_taxes({
                "amount": invoice.amount_due / 100,
                "shipping": 0,
                "to_country": invoice.customer_address.country,
                "to_zip": invoice.customer_address.postal_code
            })
            
            # Store invoice in database
            await self.execute_sql(
                f"""
                INSERT INTO invoices (
                    id, subscription_id, amount_due, tax_amount,
                    currency, status, created_at, updated_at
                ) VALUES (
                    '{invoice.id}', '{subscription_id}', {invoice.amount_due},
                    {tax_data['tax_amount'] * 100}, '{invoice.currency}',
                    'open', NOW(), NOW()
                )
                """
            )
            
            return {"success": True, "invoice": invoice}
        except Exception as e:
            self.logger.error(f"Failed to generate invoice: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def process_payment(self, invoice_id: str) -> Dict[str, Any]:
        """Process payment for an invoice."""
        try:
            # Check for fraud
            invoice = stripe.Invoice.retrieve(invoice_id)
            fraud_check = fraud_detector.check_transaction({
                "amount": invoice.amount_due,
                "currency": invoice.currency,
                "customer": invoice.customer
            })
            
            if fraud_check.get("risk_level") == "high":
                raise Exception("Potential fraud detected")
                
            # Pay invoice
            stripe.Invoice.pay(invoice_id)
            
            # Update database
            await self.execute_sql(
                f"""
                UPDATE invoices
                SET status = 'paid',
                    paid_at = NOW(),
                    updated_at = NOW()
                WHERE id = '{invoice_id}'
                """
            )
            
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to process payment: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def handle_refund(self, payment_intent_id: str, amount: Decimal) -> Dict[str, Any]:
        """Process a refund."""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=int(amount * 100)
            )
            
            await self.execute_sql(
                f"""
                INSERT INTO refunds (
                    id, payment_intent_id, amount, currency,
                    status, created_at, updated_at
                ) VALUES (
                    '{refund.id}', '{payment_intent_id}', {amount * 100},
                    '{refund.currency}', 'succeeded', NOW(), NOW()
                )
                """
            )
            
            return {"success": True, "refund": refund}
        except Exception as e:
            self.logger.error(f"Failed to process refund: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def handle_dispute(self, charge_id: str) -> Dict[str, Any]:
        """Handle payment dispute."""
        try:
            dispute = stripe.Dispute.retrieve(charge_id)
            
            await self.execute_sql(
                f"""
                INSERT INTO disputes (
                    id, charge_id, amount, currency,
                    status, created_at, updated_at
                ) VALUES (
                    '{dispute.id}', '{charge_id}', {dispute.amount},
                    '{dispute.currency}', 'needs_response', NOW(), NOW()
                )
                """
            )
            
            return {"success": True, "dispute": dispute}
        except Exception as e:
            self.logger.error(f"Failed to handle dispute: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        try:
            event = stripe.Event.construct_from(payload, stripe.api_key)
            
            if event.type == "invoice.payment_succeeded":
                await self.process_payment(event.data.object.id)
            elif event.type == "charge.refunded":
                await self.handle_refund(
                    event.data.object.payment_intent,
                    Decimal(event.data.object.amount_refunded) / 100
                )
            elif event.type == "charge.dispute.created":
                await self.handle_dispute(event.data.object.id)
                
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to process webhook: {str(e)}")
            return {"success": False, "error": str(e)}

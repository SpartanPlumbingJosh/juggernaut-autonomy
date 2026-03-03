"""
SaaS Billing Platform - Automated customer onboarding, payment processing, and service provisioning.
"""

import json
import stripe
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.database import query_db, execute_db
from core.logging import log_action

# Initialize Stripe
stripe.api_key = "sk_test_..."  # Should be from config

class SaaSPlatform:
    def __init__(self):
        self.pricing_plans = {
            "basic": {
                "price_cents": 9900,
                "features": ["core_service", "email_support"],
                "max_users": 5
            },
            "pro": {
                "price_cents": 24900,
                "features": ["core_service", "priority_support", "api_access"],
                "max_users": 25
            },
            "enterprise": {
                "price_cents": 99900,
                "features": ["core_service", "24/7_support", "api_access", "sla"],
                "max_users": 1000
            }
        }

    async def onboard_customer(self, customer_data: Dict) -> Tuple[bool, str]:
        """Handle full customer onboarding flow."""
        try:
            # 1. Create Stripe customer
            stripe_customer = stripe.Customer.create(
                email=customer_data["email"],
                name=customer_data["name"],
                metadata={
                    "signup_source": customer_data.get("source", "web"),
                    "company": customer_data.get("company", "")
                }
            )

            # 2. Create subscription
            subscription = stripe.Subscription.create(
                customer=stripe_customer.id,
                items=[{
                    "price": self._get_stripe_price_id(customer_data["plan"])
                }],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )

            # 3. Provision service
            provision_result = await self._provision_service(
                customer_data,
                stripe_customer.id,
                subscription.id
            )

            if not provision_result[0]:
                raise Exception(provision_result[1])

            # 4. Record in database
            await execute_db(
                f"""
                INSERT INTO customers (
                    id, stripe_id, name, email, company, 
                    plan, status, created_at, metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{stripe_customer.id}',
                    '{customer_data["name"].replace("'", "''")}',
                    '{customer_data["email"]}',
                    {f"'{customer_data['company'].replace("'", "''")}'" if customer_data.get("company") else "NULL"},
                    '{customer_data["plan"]}',
                    'pending',
                    NOW(),
                    '{json.dumps(customer_data.get("metadata", {})).replace("'", "''")}'::jsonb
                )
                """
            )

            log_action(
                "customer.onboarded",
                f"New customer onboarded: {customer_data['email']}",
                level="info",
                output_data={
                    "customer": stripe_customer.id,
                    "plan": customer_data["plan"]
                }
            )

            return True, subscription.latest_invoice.payment_intent.client_secret

        except Exception as e:
            log_action(
                "customer.onboarding_failed",
                f"Failed to onboard customer: {str(e)}",
                level="error",
                error_data={
                    "email": customer_data.get("email"),
                    "error": str(e)
                }
            )
            return False, str(e)

    async def _provision_service(self, customer_data: Dict, stripe_id: str, subscription_id: str) -> Tuple[bool, str]:
        """Provision service resources for new customer."""
        try:
            # TODO: Implement actual service provisioning
            # This would create accounts, allocate resources, send welcome emails, etc.
            return True, "Provisioned successfully"
        except Exception as e:
            return False, str(e)

    def _get_stripe_price_id(self, plan: str) -> str:
        """Get Stripe price ID for a plan."""
        # In a real implementation, these would be configured in Stripe
        price_ids = {
            "basic": "price_basic",
            "pro": "price_pro", 
            "enterprise": "price_enterprise"
        }
        return price_ids[plan]

    async def process_webhook(self, event_data: Dict) -> bool:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Event.construct_from(event_data, stripe.api_key)
            
            if event.type == "invoice.paid":
                await self._handle_payment_success(event.data.object)
            elif event.type == "invoice.payment_failed":
                await self._handle_payment_failure(event.data.object)
            elif event.type == "customer.subscription.deleted":
                await self._handle_subscription_cancelled(event.data.object)

            return True
        except Exception as e:
            log_action(
                "stripe.webhook_failed",
                f"Failed to process webhook: {str(e)}",
                level="error",
                error_data={"event_type": event_data.get("type")}
            )
            return False

    async def _handle_payment_success(self, invoice) -> None:
        """Handle successful payment."""
        await execute_db(
            f"""
            UPDATE customers
            SET status = 'active',
                last_payment_at = NOW(),
                updated_at = NOW()
            WHERE stripe_id = '{invoice.customer}'
            """
        )

        # Record revenue event
        await execute_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {invoice.amount_paid},
                '{invoice.currency}',
                'subscription',
                '{json.dumps({
                    "invoice_id": invoice.id,
                    "subscription_id": invoice.subscription,
                    "period_start": invoice.period_start,
                    "period_end": invoice.period_end
                }).replace("'", "''")}'::jsonb,
                NOW()
            )
            """
        )

        log_action(
            "payment.succeeded",
            f"Payment succeeded for invoice {invoice.id}",
            level="info",
            output_data={
                "amount": invoice.amount_paid,
                "customer": invoice.customer
            }
        )

    async def _handle_payment_failure(self, invoice) -> None:
        """Handle failed payment."""
        await execute_db(
            f"""
            UPDATE customers
            SET status = 'payment_failed',
                updated_at = NOW()
            WHERE stripe_id = '{invoice.customer}'
            """
        )

        log_action(
            "payment.failed",
            f"Payment failed for invoice {invoice.id}",
            level="warning",
            output_data={
                "amount": invoice.amount_due,
                "customer": invoice.customer
            }
        )

    async def _handle_subscription_cancelled(self, subscription) -> None:
        """Handle subscription cancellation."""
        await execute_db(
            f"""
            UPDATE customers
            SET status = 'cancelled',
                updated_at = NOW()
            WHERE stripe_id = '{subscription.customer}'
            """
        )

        log_action(
            "subscription.cancelled",
            f"Subscription cancelled for {subscription.customer}",
            level="info",
            output_data={"subscription_id": subscription.id}
        )

    async def get_customer_status(self, customer_id: str) -> Optional[Dict]:
        """Get customer status and subscription details."""
        try:
            result = await query_db(
                f"""
                SELECT c.*, 
                    (SELECT SUM(amount_cents) 
                     FROM revenue_events 
                     WHERE source = 'subscription' 
                     AND metadata->>'customer_id' = c.id::text) as lifetime_value_cents
                FROM customers c
                WHERE c.id = '{customer_id}'
                """
            )
            return result.get("rows", [None])[0]
        except Exception:
            return None

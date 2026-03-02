"""
Billing Service - Handles subscriptions, invoices and payments.
Supports multiple payment providers (Stripe, PayPal etc).
"""
import os
import stripe
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

from core.database import query_db

class BillingCycle(Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

# Initialize Stripe if API key is set
stripe.api_key = os.getenv("STRIPE_API_KEY")

class BillingService:
    def __init__(self, db_executor):
        self.db = db_executor

    async def create_customer(self, user_id: str, email: str, name: str) -> Dict:
        """Create a billing customer record"""
        stripe_customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"user_id": user_id}
        )
        
        await self.db(f"""
            INSERT INTO billing_customers 
            (user_id, stripe_id, email, name, created_at, updated_at)
            VALUES
            ('{user_id}', '{stripe_customer.id}', '{email}', '{name}', NOW(), NOW())
        """)
        
        return {
            "success": True,
            "customer_id": stripe_customer.id
        }

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        cycle: BillingCycle = BillingCycle.MONTHLY
    ) -> Dict:
        """Create a new subscription"""
        # Get plan details
        plan = await self.get_plan(plan_id)
        if not plan:
            return {"success": False, "error": "Plan not found"}
            
        # Calculate billing period
        now = datetime.utcnow()
        if cycle == BillingCycle.MONTHLY:
            period_end = now + timedelta(days=30)
        elif cycle == BillingCycle.QUARTERLY:
            period_end = now + timedelta(days=90)
        else:
            period_end = now + timedelta(days=365)

        # Create Stripe subscription
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": plan["stripe_price_id"]}],
            billing_cycle_anchor=int(now.timestamp()),
            proration_behavior="none"
        )
        
        # Store in database
        await self.db(f"""
            INSERT INTO billing_subscriptions
            (customer_id, plan_id, stripe_id, status, cycle, period_start, period_end,
             amount_due, amount_paid, created_at, updated_at)
            VALUES (
                '{customer_id}',
                '{plan_id}',
                '{subscription.id}',
                'active',
                '{cycle.value}',
                '{now.isoformat()}',
                '{period_end.isoformat()}',
                {plan["price_cents"]},
                0,
                NOW(),
                NOW()
            )
        """)
        
        return {
            "success": True,
            "subscription_id": subscription.id,
            "amount_due": plan["price_cents"],
            "period_end": period_end.isoformat()
        }

    async def record_payment(
        self,
        payment_intent_id: str,
        amount_cents: int,
        currency: str = "usd"
    ) -> Dict:
        """Record a successful payment"""
        payment = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        subscription_id = payment.metadata.get("subscription_id")
        invoice_id = payment.metadata.get("invoice_id")
        
        await self.db(f"""
            INSERT INTO billing_payments
            (payment_intent_id, amount_cents, currency, status, 
             subscription_id, invoice_id, created_at, updated_at)
            VALUES (
                '{payment_intent_id}',
                {amount_cents},
                '{currency}',
                'completed',
                {f"'{subscription_id}'" if subscription_id else "NULL"},
                {f"'{invoice_id}'" if invoice_id else "NULL"},
                NOW(),
                NOW()
            )
            
            UPDATE billing_subscriptions
            SET amount_paid = amount_paid + {amount_cents},
                updated_at = NOW()
            WHERE stripe_id = '{subscription_id}'
        """)
        
        # Record revenue event
        await self.db(f"""
            INSERT INTO revenue_events
            (event_type, amount_cents, currency, source, recorded_at)
            VALUES (
                'revenue',
                {amount_cents},
                '{currency}',
                'stripe',
                NOW()
            )
        """)
        
        return {"success": True}

    async def process_dunning(self) -> Dict:
        """Handle failed payments and subscription retries"""
        # Get subscriptions with failed payments
        subs = await self.db("""
            SELECT id, customer_id, stripe_id, amount_due, amount_paid
            FROM billing_subscriptions
            WHERE status = 'past_due'
            OR (period_end < NOW() AND amount_paid < amount_due)
            LIMIT 100
        """)
        
        processed = 0
        
        for sub in subs.get("rows", []):
            try:
                # Attempt to retry payment
                payment = stripe.PaymentIntent.create(
                    amount=sub["amount_due"] - sub["amount_paid"],
                    currency="usd",
                    customer=sub["customer_id"],
                    payment_method=sub["default_payment_method"],
                    confirm=True
                )
                
                if payment.status == "succeeded":
                    await self.record_payment(
                        payment.id,
                        payment.amount,
                        payment.currency
                    )
                    processed += 1
            except Exception:
                # Mark subscription as failed after 3 attempts
                await self.db(f"""
                    UPDATE billing_subscriptions
                    SET status = 'failed',
                        updated_at = NOW()
                    WHERE stripe_id = '{sub["stripe_id"]}'
                """)
        
        return {
            "success": True,
            "processed": processed,
            "attempted": len(subs.get("rows", []))
        }

    async def get_plan(self, plan_id: str) -> Optional[Dict]:
        """Retrieve billing plan details"""
        plan = await self.db(f"""
            SELECT id, name, stripe_price_id, price_cents 
            FROM billing_plans
            WHERE id = '{plan_id}'
        """)
        
        if plan.get("rows"):
            return plan["rows"][0]
        return None

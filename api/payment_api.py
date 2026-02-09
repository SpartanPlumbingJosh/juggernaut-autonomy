"""
Payment Processing API - Handles Stripe/PayPal integrations, subscriptions, and webhooks.
"""

import json
import stripe
import paypalrestsdk
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db, execute_db

# Initialize payment providers
stripe.api_key = "sk_test_..."  # Load from environment
paypalrestsdk.configure({
    "mode": "sandbox",  # Load from environment
    "client_id": "...",
    "client_secret": "..."
})

async def create_customer(email: str, payment_method: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a customer in payment systems."""
    try:
        # Create Stripe customer
        stripe_customer = stripe.Customer.create(
            email=email,
            metadata=metadata or {}
        )
        
        # Create PayPal customer
        paypal_customer = paypalrestsdk.Customer({
            "email": email,
            "metadata": metadata or {}
        })
        if paypal_customer.create():
            paypal_id = paypal_customer.id
        else:
            paypal_id = None
            
        # Store in database
        await execute_db(
            f"""
            INSERT INTO customers (
                id, email, stripe_id, paypal_id, 
                created_at, updated_at, metadata
            ) VALUES (
                gen_random_uuid(),
                '{email}',
                '{stripe_customer.id}',
                {f"'{paypal_id}'" if paypal_id else "NULL"},
                NOW(),
                NOW(),
                '{json.dumps(metadata or {})}'
            )
            RETURNING id
            """
        )
        
        return {"success": True, "stripe_id": stripe_customer.id, "paypal_id": paypal_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def create_subscription(customer_id: str, plan_id: str, payment_method: str) -> Dict[str, Any]:
    """Create a subscription for a customer."""
    try:
        # Get customer details
        customer_res = await query_db(
            f"SELECT stripe_id, paypal_id FROM customers WHERE id = '{customer_id}'"
        )
        customer = customer_res.get("rows", [{}])[0]
        
        if payment_method == "stripe":
            # Create Stripe subscription
            subscription = stripe.Subscription.create(
                customer=customer["stripe_id"],
                items=[{"price": plan_id}],
                expand=["latest_invoice.payment_intent"]
            )
            
            # Store in database
            await execute_db(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, provider_id, plan_id,
                    status, start_date, current_period_end,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{subscription.id}',
                    '{plan_id}',
                    'active',
                    NOW(),
                    '{datetime.fromtimestamp(subscription.current_period_end).isoformat()}',
                    NOW(),
                    NOW()
                )
                """
            )
            
            return {"success": True, "subscription_id": subscription.id}
            
        elif payment_method == "paypal":
            # Create PayPal subscription
            subscription = paypalrestsdk.Subscription({
                "plan_id": plan_id,
                "subscriber": {
                    "email": customer["email"]
                }
            })
            if subscription.create():
                # Store in database
                await execute_db(
                    f"""
                    INSERT INTO subscriptions (
                        id, customer_id, provider_id, plan_id,
                        status, start_date, current_period_end,
                        created_at, updated_at
                    ) VALUES (
                        gen_random_uuid(),
                        '{customer_id}',
                        '{subscription.id}',
                        '{plan_id}',
                    'active',
                    NOW(),
                    '{datetime.fromtimestamp(subscription.current_period_end).isoformat()}',
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True, "subscription_id": subscription.id}
        else:
            return {"success": False, "error": subscription.error}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

async def handle_payment_webhook(event: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Handle payment provider webhooks."""
    try:
        if provider == "stripe":
            # Verify Stripe event
            event = stripe.Webhook.construct_event(
                event["body"], event["headers"]["Stripe-Signature"], stripe.webhook_secret
            )
            
            # Handle event types
            if event["type"] == "payment_intent.succeeded":
                await handle_successful_payment(event["data"]["object"])
            elif event["type"] == "invoice.payment_failed":
                await handle_failed_payment(event["data"]["object"])
            elif event["type"] == "customer.subscription.deleted":
                await handle_subscription_cancelled(event["data"]["object"])
                
        elif provider == "paypal":
            # Verify PayPal event
            if not paypalrestsdk.WebhookEvent.verify(
                event["headers"]["Paypal-Transmission-Id"],
                event["headers"]["Paypal-Transmission-Time"],
                event["headers"]["Paypal-Transmission-Sig"],
                event["body"],
                paypalrestsdk.webhook_secret
            ):
                return {"success": False, "error": "Invalid signature"}
            
            # Handle event types
            if event["event_type"] == "PAYMENT.SALE.COMPLETED":
                await handle_successful_payment(event["resource"])
            elif event["event_type"] == "PAYMENT.SALE.DENIED":
                await handle_failed_payment(event["resource"])
            elif event["event_type"] == "BILLING.SUBSCRIPTION.CANCELLED":
                await handle_subscription_cancelled(event["resource"])
                
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def handle_successful_payment(payment: Dict[str, Any]) -> None:
    """Handle successful payment."""
    await execute_db(
        f"""
        INSERT INTO payments (
            id, customer_id, amount, currency,
            payment_method, status, provider_id,
            created_at, updated_at
        ) VALUES (
            gen_random_uuid(),
            '{payment["customer"]}',
            {payment["amount"]},
            '{payment["currency"]}',
            '{payment["payment_method"]}',
            'succeeded',
            '{payment["id"]}',
            NOW(),
            NOW()
        )
        """
    )

async def handle_failed_payment(payment: Dict[str, Any]) -> None:
    """Handle failed payment."""
    await execute_db(
        f"""
        INSERT INTO payments (
            id, customer_id, amount, currency,
            payment_method, status, provider_id,
            created_at, updated_at
        ) VALUES (
            gen_random_uuid(),
            '{payment["customer"]}',
            {payment["amount"]},
            '{payment["currency"]}',
            '{payment["payment_method"]}',
            'failed',
            '{payment["id"]}',
            NOW(),
            NOW()
        )
        """
    )

async def handle_subscription_cancelled(subscription: Dict[str, Any]) -> None:
    """Handle subscription cancellation."""
    await execute_db(
        f"""
        UPDATE subscriptions
        SET status = 'cancelled',
            updated_at = NOW()
        WHERE provider_id = '{subscription["id"]}'
        """
    )

async def generate_invoice(customer_id: str, period_start: str, period_end: str) -> Dict[str, Any]:
    """Generate an invoice for a customer."""
    try:
        # Get customer details
        customer_res = await query_db(
            f"SELECT stripe_id, paypal_id FROM customers WHERE id = '{customer_id}'"
        )
        customer = customer_res.get("rows", [{}])[0]
        
        # Get payments for period
        payments_res = await query_db(
            f"""
            SELECT SUM(amount) as total_amount, currency
            FROM payments
            WHERE customer_id = '{customer_id}'
              AND created_at BETWEEN '{period_start}' AND '{period_end}'
            GROUP BY currency
            """
        )
        payments = payments_res.get("rows", [])
        
        # Generate invoice
        invoice = {
            "customer_id": customer_id,
            "period_start": period_start,
            "period_end": period_end,
            "payments": payments,
            "total": sum(p["total_amount"] for p in payments)
        }
        
        # Store invoice
        await execute_db(
            f"""
            INSERT INTO invoices (
                id, customer_id, period_start, period_end,
                total_amount, currency, status,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_id}',
                '{period_start}',
                '{period_end}',
                {invoice["total"]},
                '{payments[0]["currency"] if payments else "USD"}',
                'generated',
                NOW(),
                NOW()
            )
            """
        )
        
        return {"success": True, "invoice": invoice}
    except Exception as e:
        return {"success": False, "error": str(e)}

__all__ = [
    "create_customer",
    "create_subscription",
    "handle_payment_webhook",
    "generate_invoice"
]

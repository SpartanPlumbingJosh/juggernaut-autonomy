import hashlib
from fastapi import HTTPException, Request
from typing import Dict, Any
from datetime import datetime

from billing.models import Subscription, Invoice, UsageRecord
from core.database import query_db

async def handle_stripe_webhook(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe webhook events with idempotency checks."""
    event_id = payload.get("id")
    event_type = payload.get("type")
    
    # Check if we've already processed this event
    existing = await query_db(
        f"SELECT id FROM webhook_events WHERE id = '{event_id}' LIMIT 1"
    )
    if existing.get("rows"):
        return {"status": "already_processed"}
    
    # Handle different event types
    try:
        if event_type == "customer.subscription.updated":
            data = payload["data"]["object"]
            subscription = Subscription(**data)
            await _update_subscription(subscription)
            
        elif event_type == "invoice.payment_succeeded":
            data = payload["data"]["object"]
            invoice = Invoice(**data)
            await _record_invoice_payment(invoice)
            
        elif event_type == "customer.subscription.deleted":
            data = payload["data"]["object"]
            subscription = Subscription(**data)
            await _cancel_subscription(subscription)
            
        elif event_type == "invoice.payment_failed":
            data = payload["data"]["object"]
            invoice = Invoice(**data)
            await _handle_payment_failure(invoice)
            
        # Record the webhook event
        await query_db(
            f"""
            INSERT INTO webhook_events (id, type, payload, created_at)
            VALUES ('{event_id}', '{event_type}', '{json.dumps(payload)}', NOW())
            """
        )
        
        return {"status": "processed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def _update_subscription(subscription: Subscription) -> None:
    """Update subscription status and details."""
    await query_db(
        f"""
        INSERT INTO subscriptions (id, customer_id, plan_id, status, current_period_start, 
            current_period_end, cancel_at_period_end, metadata, updated_at)
        VALUES ('{subscription.id}', '{subscription.customer_id}', '{subscription.plan_id}', 
            '{subscription.status}', '{subscription.current_period_start.isoformat()}', 
            '{subscription.current_period_end.isoformat()}', {subscription.cancel_at_period_end}, 
            '{json.dumps(subscription.metadata)}', NOW())
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            current_period_start = EXCLUDED.current_period_start,
            current_period_end = EXCLUDED.current_period_end,
            cancel_at_period_end = EXCLUDED.cancel_at_period_end,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        """
    )

async def _record_invoice_payment(invoice: Invoice) -> None:
    """Record successful invoice payment."""
    await query_db(
        f"""
        INSERT INTO revenue_events (id, event_type, amount_cents, currency, source, 
            recorded_at, metadata)
        VALUES ('{invoice.id}', 'revenue', {invoice.amount_paid_cents}, '{invoice.currency}', 
            'stripe', '{invoice.period_end.isoformat()}', '{json.dumps(invoice.metadata)}')
        """
    )

async def _cancel_subscription(subscription: Subscription) -> None:
    """Handle subscription cancellation."""
    await query_db(
        f"""
        UPDATE subscriptions 
        SET status = 'canceled', updated_at = NOW()
        WHERE id = '{subscription.id}'
        """
    )

async def _handle_payment_failure(invoice: Invoice) -> None:
    """Handle failed payment attempts."""
    await query_db(
        f"""
        INSERT INTO revenue_events (id, event_type, amount_cents, currency, source, 
            recorded_at, metadata)
        VALUES ('{invoice.id}', 'payment_failed', {invoice.amount_due_cents}, '{invoice.currency}', 
            'stripe', '{invoice.period_end.isoformat()}', '{json.dumps(invoice.metadata)}')
        """
    )

"""
Billing API - Handle metered usage, subscriptions and invoices.

Endpoints:
- GET /billing/usage - Current usage stats
- POST /billing/subscription - Create/update subscription
- GET /billing/invoices - List invoices
- GET /billing/invoices/<id> - Get invoice PDF
- POST /billing/webhook - Handle payment provider webhooks
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import stripe

from core.database import query_db
from core.utils import get_config


def initialize_stripe():
    """Initialize Stripe with API key."""
    stripe.api_key = get_config('STRIPE_SECRET_KEY')


def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }


async def handle_usage_request(account_id: str) -> Dict[str, Any]:
    """Get current usage metrics for account."""
    try:
        sql = f"""
        SELECT 
            metrics.current_period_usage,
            metrics.current_period_start,
            metrics.current_period_end,
            metrics.metered_features,
            plans.plan_id,
            plans.plan_name,
            plans.plan_limits
        FROM account_billing_metrics metrics
        JOIN account_billing_plans plans ON metrics.plan_id = plans.plan_id
        WHERE metrics.account_id = '{account_id}'
        """
        result = await query_db(sql)
        data = result.get("rows", [{}])[0]
        return _make_response(200, data)
    except Exception as e:
        return _make_response(500, {"error": str(e)})


async def handle_subscription_request(account_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update subscription."""
    try:
        plan_id = body.get('plan_id')
        payment_method = body.get('payment_method')
        
        # Check if existing subscription
        sql = f"""
        SELECT customer_id, subscription_id 
        FROM account_billing_plans 
        WHERE account_id = '{account_id}'
        """
        result = await query_db(sql)
        existing = result.get("rows", [{}])[0]
        
        if existing.get('customer_id'):
            # Update existing subscription
            stripe.Subscription.modify(
                existing['subscription_id'],
                items=[{
                    'price': plan_id,
                    'quantity': 1
                }],
                default_payment_method=payment_method
            )
            action = 'updated'
        else:
            # Create new subscription
            customer = stripe.Customer.create(
                email=body.get('email'),
                payment_method=payment_method,
                invoice_settings={
                    'default_payment_method': payment_method
                }
            )
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': plan_id}],
                expand=['latest_invoice.payment_intent']
            )
            await query_db(
                f"""
                INSERT INTO account_billing_plans (
                    account_id, plan_id, customer_id, 
                    subscription_id, created_at
                ) VALUES (
                    '{account_id}', '{plan_id}', '{customer.id}',
                    '{subscription.id}', NOW()
                )
                """
            )
            action = 'created'
            
        return _make_response(200, {"status": f"Subscription {action}", "plan_id": plan_id})
    except Exception as e:
        return _make_response(500, {"error": str(e)})


async def handle_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Stripe webhook events."""
    try:
        event_type = event['type']
        
        if event_type == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            await query_db(
                f"""
                INSERT INTO billing_invoices (
                    invoice_id, account_id, amount_paid,
                    currency, period_start, period_end,
                    hosted_invoice_url, status, created_at
                ) VALUES (
                    '{invoice['id']}', '{invoice['customer']}', {invoice['amount_paid']/100},
                    '{invoice['currency']}', {invoice['period_start']}, {invoice['period_end']},
                    '{invoice['hosted_invoice_url']}', 'paid', NOW()
                )
                """
            )

        # Handle other payment lifecycle events
        elif event_type.startswith('customer.subscription'):
            subscription = event['data']['object']
            await query_db(
                f"""
                UPDATE account_billing_plans 
                SET status = '{subscription['status']}',
                    current_period_end = {subscription['current_period_end']}
                WHERE subscription_id = '{subscription['id']}'
                """
            )
            
        return _make_response(200, {"status": "Webhook processed"})
    except Exception as e:
        return _make_response(500, {"error": str(e)})


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[Dict]) -> Dict[str, Any]:
    """Route billing API requests."""
    account_id = query_params.get('account_id') 
    if not account_id:
        return _make_response(400, {"error": "Missing account_id"})

    # GET /billing/usage
    if path.endswith('/usage') and method == 'GET':
        return handle_usage_request(account_id)
        
    # POST /billing/subscription
    elif path.endswith('/subscription') and method == 'POST':
        return handle_subscription_request(account_id, body)
        
    # POST /billing/webhook
    elif path.endswith('/webhook') and method == 'POST':
        return handle_webhook(body)
        
    return _make_response(404, {"error": "Not found"})


__all__ = ["route_request", "initialize_stripe"]

"""
Automated API Service - Generate revenue through API access tiers.

Features:
- Tiered subscription payments via Stripe
- Usage tracking
- Automatic revenue logging
"""

import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import HTTPException
from ..core.database import query_db

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# API Pricing Tiers (cents/month)
API_TIERS = {
    'basic': 9900,    # $99/month
    'pro': 24900,     # $249/month 
    'enterprise': 99900  # $999/month
}

async def create_subscription(customer_email: str, tier: str) -> Dict[str, Any]:
    """Create a new API subscription"""
    if tier not in API_TIERS:
        raise HTTPException(status_code=400, detail="Invalid tier specified")
    
    try:
        # Create Stripe customer
        customer = stripe.Customer.create(email=customer_email)
        
        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{
                'price_data': {
                    'currency': 'usd',
                    'product': os.getenv('STRIPE_PRODUCT_ID'),
                    'recurring': {'interval': 'month'},
                    'unit_amount': API_TIERS[tier],
                },
            }],
            payment_behavior='default_incomplete',
            expand=['latest_invoice.payment_intent']
        )
        
        # Log initial transaction
        await log_revenue_event(
            source="api_subscription",
            event_type="revenue",
            amount_cents=API_TIERS[tier],
            currency="usd",
            metadata={
                "tier": tier,
                "customer_email": customer_email,
                "stripe_customer_id": customer.id,
                "subscription_id": subscription.id
            }
        )
        
        return {
            "subscription_id": subscription.id,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret,
            "tier": tier,
            "amount_cents": API_TIERS[tier]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment processing failed: {str(e)}")


async def handle_webhook(payload: bytes, sig_header: str) -> bool:
    """Process Stripe webhooks for subscription events"""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle payment success
    if event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        await log_revenue_event(
            source="api_subscription_renewal",
            event_type="revenue",
            amount_cents=invoice['amount_paid'],
            currency=invoice['currency'],
            metadata={
                "stripe_invoice_id": invoice['id'],
                "customer_email": invoice['customer_email'],
                "period_start": invoice['period_start'],
                "period_end": invoice['period_end']
            }
        )
    
    return True


async def log_revenue_event(
    source: str,
    event_type: str,
    amount_cents: int,
    currency: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Log revenue event to database"""
    try:
        metadata_json = json.dumps(metadata or {})
        await query_db(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(), 
                '{event_type}',
                {amount_cents},
                '{currency}',
                '{source}',
                '{metadata_json}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
        return True
    except Exception as e:
        print(f"Failed to log revenue event: {str(e)}")
        return False


async def get_api_usage(customer_id: str) -> Dict[str, Any]:
    """Get API usage metrics for customer"""
    try:
        result = await query_db(
            f"""
            SELECT COUNT(*) as call_count, 
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                   SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) as error_count
            FROM api_usage_logs
            WHERE customer_id = '{customer_id}'
              AND recorded_at >= NOW() - INTERVAL '30 days'
            """
        )
        return result.get("rows", [{}])[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage data: {str(e)}")

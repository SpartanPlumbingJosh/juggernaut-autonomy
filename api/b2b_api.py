"""
B2B API Service - Automated revenue stream for API/service access.
Includes authentication, billing, usage tracking, and invoicing.
"""

import os
import json
import stripe
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.database import query_db, execute_db
from api.revenue_api import _make_response, _error_response

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class B2BAPIService:
    """Core B2B API service handling subscriptions, usage and billing."""
    
    def __init__(self):
        self.base_price = 1000  # $10/month base price
        self.price_per_call = 1  # $0.01 per API call
        
    async def create_customer(self, email: str, payment_method: str) -> Dict[str, Any]:
        """Create a new Stripe customer and subscription."""
        try:
            # Create Stripe customer
            customer = stripe.Customer.create(
                email=email,
                payment_method=payment_method,
                invoice_settings={
                    'default_payment_method': payment_method
                }
            )
            
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product': os.getenv("STRIPE_PRODUCT_ID"),
                        'recurring': {'interval': 'month'},
                        'unit_amount': self.base_price,
                    },
                }],
                expand=['latest_invoice.payment_intent']
            )
            
            # Store customer in database
            await execute_db(
                f"""
                INSERT INTO b2b_customers 
                (id, email, stripe_id, created_at)
                VALUES (gen_random_uuid(), '{email}', '{customer.id}', NOW())
                """
            )
            
            return {
                "customer_id": customer.id,
                "subscription_id": subscription.id,
                "status": subscription.status
            }
            
        except stripe.error.StripeError as e:
            return {"error": str(e)}
            
    async def track_usage(self, customer_id: str, endpoint: str) -> Dict[str, Any]:
        """Track API usage for billing."""
        try:
            # Record usage
            await execute_db(
                f"""
                INSERT INTO b2b_usage 
                (id, customer_id, endpoint, timestamp)
                VALUES (gen_random_uuid(), '{customer_id}', '{endpoint}', NOW())
                """
            )
            
            # Get current billing period usage
            period_start = datetime.utcnow().replace(day=1)
            usage_count = await query_db(
                f"""
                SELECT COUNT(*) as count
                FROM b2b_usage
                WHERE customer_id = '{customer_id}'
                AND timestamp >= '{period_start.isoformat()}'
                """
            )
            
            # Update Stripe subscription with usage
            stripe.SubscriptionItem.create_usage_record(
                os.getenv("STRIPE_SUBSCRIPTION_ITEM_ID"),
                quantity=usage_count.get("rows", [{}])[0].get("count", 0),
                timestamp=int(datetime.utcnow().timestamp())
            )
            
            return {"success": True}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def generate_invoice(self, customer_id: str) -> Dict[str, Any]:
        """Generate and send invoice for customer."""
        try:
            # Get customer details
            customer = await query_db(
                f"""
                SELECT stripe_id 
                FROM b2b_customers
                WHERE id = '{customer_id}'
                """
            )
            stripe_id = customer.get("rows", [{}])[0].get("stripe_id")
            
            if not stripe_id:
                return {"error": "Customer not found"}
                
            # Create invoice
            invoice = stripe.Invoice.create(
                customer=stripe_id,
                auto_advance=True
            )
            
            # Record invoice in revenue tracking
            await execute_db(
                f"""
                INSERT INTO revenue_events 
                (id, event_type, amount_cents, currency, source, recorded_at)
                VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {invoice.amount_due},
                    '{invoice.currency}',
                    'b2b_api',
                    NOW()
                )
                """
            )
            
            return {
                "invoice_id": invoice.id,
                "amount": invoice.amount_due,
                "status": invoice.status
            }
            
        except stripe.error.StripeError as e:
            return {"error": str(e)}
            
    async def handle_api_request(self, path: str, method: str, headers: Dict[str, str], body: Optional[str] = None) -> Dict[str, Any]:
        """Route B2B API requests."""
        # Authentication
        api_key = headers.get("X-API-KEY")
        if not api_key:
            return _error_response(401, "API key required")
            
        # Get customer
        customer = await query_db(
            f"""
            SELECT id 
            FROM b2b_customers
            WHERE api_key = '{api_key}'
            """
        )
        customer_id = customer.get("rows", [{}])[0].get("id")
        if not customer_id:
            return _error_response(401, "Invalid API key")
            
        # Track usage
        await self.track_usage(customer_id, path)
        
        # Handle request
        if path == "/subscription":
            if method == "POST":
                return await self.create_customer(body.get("email"), body.get("payment_method"))
            elif method == "GET":
                return await self.get_subscription(customer_id)
                
        elif path == "/invoice":
            if method == "POST":
                return await self.generate_invoice(customer_id)
                
        return _error_response(404, "Not found")

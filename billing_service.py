"""
Billing Service - Handles payment processing, subscriptions, and invoicing.
Integrated with Stripe for PCI-compliant payment processing.
"""

import datetime
import json
from typing import Any, Dict, List, Optional, Tuple

import stripe
from dateutil.relativedelta import relativedelta

from core.database import query_db

# Initialize Stripe
stripe.api_key = "sk_test_YOUR_STRIPE_SECRET_KEY"  # Should be from config/environment

class BillingService:
    """Core billing operations and subscription management."""
    
    @staticmethod
    async def create_customer(email: str, name: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            
            await query_db(
                f"""
                INSERT INTO billing_customers (id, stripe_id, email, name, metadata, created_at)
                VALUES (
                    gen_random_uuid(),
                    '{customer.id}',
                    '{email.replace("'", "''")}',
                    '{name.replace("'", "''")}',
                    '{json.dumps(metadata or {}).replace("'", "''")}'::jsonb,
                    NOW()
                )
                """
            )
            
            return customer
        except Exception as e:
            raise ValueError(f"Failed to create customer: {str(e)}")

    @staticmethod
    async def create_subscription(customer_id: str, price_id: str, quantity: int = 1) -> Dict[str, Any]:
        """Create a subscription for a customer."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id, "quantity": quantity}],
                automatic_tax={"enabled": True},
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            
            invoice = subscription.latest_invoice
            invoice_url = invoice.hosted_invoice_url or ""
            
            await query_db(
                f"""
                INSERT INTO billing_subscriptions (id, stripe_id, customer_id, status, current_period_end, 
                                                 invoice_url, metadata, created_at)
                VALUES (
                    gen_random_uuid(),
                    '{subscription.id}',
                    '{customer_id}',
                    'incomplete',
                    to_timestamp({subscription.current_period_end}),
                    {'NULL' if not invoice_url else f"'{invoice_url.replace("'", "''")}'"},
                    '{json.dumps(subscription).replace("'", "''")}'::jsonb,
                    NOW()
                )
                """
            )
            
            return {
                "subscription": subscription,
                "invoice": invoice,
                "client_secret": invoice.payment_intent.client_secret
            }
        except Exception as e:
            raise ValueError(f"Failed to create subscription: {str(e)}")

    @staticmethod
    async def record_payment_event(event_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Record a payment event and handle revenue recognition."""
        try:
            event_type = event_data.get("type", "")
            amount = float(event_data.get("amount", 0)) / 100  # Convert from cents to dollars
            currency = event_data.get("currency", "usd")
            metadata = event_data.get("metadata", {})
            
            # Revenue recognition rules based on payment type
            recognition_schedule = "immediate"
            if event_type == "subscription_payment":
                recognition_schedule = "monthly"
            
            await query_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source, metadata,
                    recognition_schedule, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(amount * 100)},  -- Convert dollars back to cents for DB
                    '{currency}',
                    'stripe',
                    '{json.dumps(metadata).replace("'", "''")}'::jsonb,
                    '{recognition_schedule}',
                    NOW(),
                    NOW()
                )
                """
            )
            
            return True, None
        except Exception as e:
            return False, {"error": str(e)}

    @staticmethod
    async def generate_invoice(items: List[Dict[str, Any]], customer_id: str) -> Dict[str, Any]:
        """Generate an invoice with line items."""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                collection_method="send_invoice",
                days_until_due=30,
                auto_advance=True
            )
            
            for item in items:
                stripe.InvoiceItem.create(
                    customer=customer_id,
                    invoice=invoice.id,
                    price=item["price_id"],
                    quantity=item["quantity"],
                    description=item.get("description", "")
                )
            
            stripe.Invoice.finalize_invoice(invoice.id)
            stripe.Invoice.send_invoice(invoice.id)
            
            return invoice
        except Exception as e:
            raise ValueError(f"Failed to generate invoice: {str(e)}")

    @staticmethod
    async def recognize_monthly_revenue() -> Dict[str, Any]:
        """Execute monthly revenue recognition for subscriptions."""
        try:
            # Get unprocessed deferred revenue
            result = await query_db("""
                SELECT id, amount_cents, metadata
                FROM revenue_events
                WHERE recognition_schedule = 'monthly'
                AND recognized = FALSE
                AND recorded_at < NOW() - INTERVAL '1 month'
            """)
            
            recognized = []
            for row in result.get("rows", []):
                event_id = row["id"]
                amount = float(row["amount_cents"]) / 12  # Monthly amortization
                
                await query_db(f"""
                    INSERT INTO recognized_revenue (
                        id, event_id, amount_cents, recognized_at
                    ) VALUES (
                        gen_random_uuid(),
                        '{event_id}',
                        {int(amount)},
                        NOW()
                    )
                """)
                
                await query_db(f"""
                    UPDATE revenue_events
                    SET recognized = TRUE
                    WHERE id = '{event_id}'
                """)
                
                recognized.append(event_id)
            
            return {
                "success": True,
                "recognized": len(recognized)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

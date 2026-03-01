"""
Billing Operations - Handle subscription management, invoicing, and payment processing.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

async def create_subscription(customer_id: str, plan_id: str, payment_method_id: str) -> Dict[str, Any]:
    """Create a new subscription for a customer."""
    try:
        # Create subscription record
        subscription_sql = f"""
        INSERT INTO subscriptions (
            id, customer_id, plan_id, status, 
            start_date, end_date, created_at
        ) VALUES (
            gen_random_uuid(),
            '{customer_id}',
            '{plan_id}',
            'active',
            NOW(),
            NOW() + INTERVAL '1 month',
            NOW()
        )
        RETURNING id
        """
        subscription_result = await query_db(subscription_sql)
        subscription_id = subscription_result.get("rows", [{}])[0].get("id")
        
        # Create initial invoice
        invoice_sql = f"""
        INSERT INTO invoices (
            id, subscription_id, amount_cents, 
            currency, status, due_date, created_at
        ) VALUES (
            gen_random_uuid(),
            '{subscription_id}',
            1000,  # Example amount
            'usd',
            'pending',
            NOW() + INTERVAL '7 days',
            NOW()
        )
        RETURNING id
        """
        await query_db(invoice_sql)
        
        # Process payment
        payment_sql = f"""
        INSERT INTO payments (
            id, invoice_id, amount_cents, 
            currency, payment_method_id, status, created_at
        ) VALUES (
            gen_random_uuid(),
            '{subscription_id}',
            1000,
            'usd',
            '{payment_method_id}',
            'pending',
            NOW()
        )
        """
        await query_db(payment_sql)
        
        return {"success": True, "subscription_id": subscription_id}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

async def process_payment(invoice_id: str, payment_method_id: str) -> Dict[str, Any]:
    """Process a payment for an invoice."""
    try:
        # Get invoice details
        invoice_sql = f"SELECT * FROM invoices WHERE id = '{invoice_id}'"
        invoice_result = await query_db(invoice_sql)
        invoice = invoice_result.get("rows", [{}])[0]
        
        if not invoice:
            return {"success": False, "error": "Invoice not found"}
        
        # Create payment record
        payment_sql = f"""
        INSERT INTO payments (
            id, invoice_id, amount_cents, 
            currency, payment_method_id, status, created_at
        ) VALUES (
            gen_random_uuid(),
            '{invoice_id}',
            {invoice.get("amount_cents")},
            '{invoice.get("currency")}',
            '{payment_method_id}',
            'pending',
            NOW()
        )
        RETURNING id
        """
        payment_result = await query_db(payment_sql)
        payment_id = payment_result.get("rows", [{}])[0].get("id")
        
        # Update invoice status
        update_sql = f"""
        UPDATE invoices
        SET status = 'paid',
            paid_at = NOW()
        WHERE id = '{invoice_id}'
        """
        await query_db(update_sql)
        
        return {"success": True, "payment_id": payment_id}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

async def cancel_subscription(subscription_id: str) -> Dict[str, Any]:
    """Cancel a subscription."""
    try:
        # Update subscription status
        sql = f"""
        UPDATE subscriptions
        SET status = 'canceled',
            end_date = NOW()
        WHERE id = '{subscription_id}'
        """
        await query_db(sql)
        
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_subscription_details(subscription_id: str) -> Dict[str, Any]:
    """Get details for a subscription."""
    try:
        sql = f"""
        SELECT s.*, p.name as plan_name, p.price_cents
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.id = '{subscription_id}'
        """
        result = await query_db(sql)
        subscription = result.get("rows", [{}])[0]
        
        if not subscription:
            return {"success": False, "error": "Subscription not found"}
        
        return {"success": True, "subscription": subscription}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

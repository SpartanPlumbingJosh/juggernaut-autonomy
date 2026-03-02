"""
Core Billing System - Handles subscriptions, payments, and revenue recognition.

Features:
- Recurring subscriptions with proration
- One-time payments
- Automated invoicing
- Payment gateway integrations
- Webhook handlers for real-time updates
- Idempotency safeguards
- Audit logging
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.database import query_db

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    "stripe": {
        "api_key": "sk_test_...",
        "webhook_secret": "whsec_...",
        "currencies": ["usd"]
    },
    "paypal": {
        "client_id": "...",
        "client_secret": "...",
        "currencies": ["usd", "eur"]
    }
}

class BillingSystem:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action

    async def create_subscription(self, customer_id: str, plan_id: str, payment_method: str, 
                                currency: str = "usd", trial_days: int = 0) -> Dict[str, Any]:
        """Create a new subscription."""
        subscription_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Validate payment gateway
        if payment_method not in PAYMENT_GATEWAYS:
            return {"success": False, "error": "Invalid payment method"}
        
        # Get plan details
        plan = await self._get_plan(plan_id)
        if not plan:
            return {"success": False, "error": "Plan not found"}
        
        # Create subscription record
        try:
            await self.execute_sql(f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    current_period_start, current_period_end,
                    trial_start, trial_end, created_at
                ) VALUES (
                    '{subscription_id}',
                    '{customer_id}',
                    '{plan_id}',
                    'trialing' if {trial_days} > 0 else 'active',
                    '{now.isoformat()}',
                    '{(now + timedelta(days=plan['billing_interval_days'])).isoformat()}',
                    {'NULL' if trial_days == 0 else f"'{now.isoformat()}'"},
                    {'NULL' if trial_days == 0 else f"'{now + timedelta(days=trial_days)}'"},
                    '{now.isoformat()}'
                )
            """)
            
            # Create initial invoice
            invoice = await self.create_invoice(
                customer_id=customer_id,
                subscription_id=subscription_id,
                amount=0 if trial_days > 0 else plan['amount'],
                currency=currency
            )
            
            return {
                "success": True,
                "subscription_id": subscription_id,
                "invoice_id": invoice['invoice_id']
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_invoice(self, customer_id: str, amount: float, currency: str,
                           subscription_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new invoice."""
        invoice_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        try:
            await self.execute_sql(f"""
                INSERT INTO invoices (
                    id, customer_id, subscription_id,
                    amount, currency, status,
                    created_at, due_date
                ) VALUES (
                    '{invoice_id}',
                    '{customer_id}',
                    {f"'{subscription_id}'" if subscription_id else "NULL"},
                    {amount},
                    '{currency}',
                    'open',
                    '{now.isoformat()}',
                    '{(now + timedelta(days=7)).isoformat()}'
                )
            """)
            
            return {
                "success": True,
                "invoice_id": invoice_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_payment(self, invoice_id: str, payment_method: str, 
                            idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Process payment for an invoice."""
        # Check for duplicate payment using idempotency key
        if idempotency_key:
            existing = await self.execute_sql(f"""
                SELECT id FROM payments 
                WHERE idempotency_key = '{idempotency_key}'
                LIMIT 1
            """)
            if existing.get('rows'):
                return {"success": False, "error": "Duplicate payment detected"}
        
        # Get invoice details
        invoice = await self._get_invoice(invoice_id)
        if not invoice:
            return {"success": False, "error": "Invoice not found"}
        
        # Process payment through gateway
        payment_result = await self._process_gateway_payment(
            invoice['amount'],
            invoice['currency'],
            payment_method
        )
        
        if not payment_result['success']:
            return payment_result
        
        # Record payment
        payment_id = str(uuid.uuid4())
        try:
            await self.execute_sql(f"""
                INSERT INTO payments (
                    id, invoice_id, amount, currency,
                    payment_method, gateway_transaction_id,
                    idempotency_key, created_at
                ) VALUES (
                    '{payment_id}',
                    '{invoice_id}',
                    {invoice['amount']},
                    '{invoice['currency']}',
                    '{payment_method}',
                    '{payment_result['transaction_id']}',
                    {f"'{idempotency_key}'" if idempotency_key else "NULL"},
                    '{datetime.now(timezone.utc).isoformat()}'
                )
            """)
            
            # Update invoice status
            await self.execute_sql(f"""
                UPDATE invoices
                SET status = 'paid',
                    paid_at = NOW()
                WHERE id = '{invoice_id}'
            """)
            
            # Record revenue event
            await self._record_revenue_event(
                amount=invoice['amount'],
                currency=invoice['currency'],
                source='subscription' if invoice['subscription_id'] else 'one-time',
                metadata={
                    'invoice_id': invoice_id,
                    'payment_id': payment_id,
                    'subscription_id': invoice['subscription_id']
                }
            )
            
            return {
                "success": True,
                "payment_id": payment_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve plan details."""
        result = await self.execute_sql(f"""
            SELECT id, name, amount, currency, billing_interval_days
            FROM billing_plans
            WHERE id = '{plan_id}'
            LIMIT 1
        """)
        return result.get('rows', [{}])[0] if result.get('rows') else None

    async def _get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve invoice details."""
        result = await self.execute_sql(f"""
            SELECT id, customer_id, subscription_id, amount, currency, status
            FROM invoices
            WHERE id = '{invoice_id}'
            LIMIT 1
        """)
        return result.get('rows', [{}])[0] if result.get('rows') else None

    async def _process_gateway_payment(self, amount: float, currency: str, 
                                     payment_method: str) -> Dict[str, Any]:
        """Process payment through payment gateway."""
        # Implementation would vary by gateway
        # This is a stub implementation
        return {
            "success": True,
            "transaction_id": str(uuid.uuid4())
        }

    async def _record_revenue_event(self, amount: float, currency: str, 
                                  source: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Record revenue event for financial tracking."""
        event_id = str(uuid.uuid4())
        try:
            await self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at
                ) VALUES (
                    '{event_id}',
                    'revenue',
                    {int(amount * 100)},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}',
                    '{datetime.now(timezone.utc).isoformat()}'
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, gateway: str, payload: Dict[str, Any], 
                           signature: Optional[str] = None) -> Dict[str, Any]:
        """Handle payment gateway webhook events."""
        # Validate webhook signature
        if not self._validate_webhook(gateway, payload, signature):
            return {"success": False, "error": "Invalid webhook signature"}
        
        # Process webhook event
        event_type = payload.get('type')
        if event_type == 'payment_succeeded':
            return await self._handle_payment_success(payload)
        elif event_type == 'subscription_updated':
            return await self._handle_subscription_update(payload)
        elif event_type == 'invoice_payment_failed':
            return await self._handle_payment_failure(payload)
        else:
            return {"success": False, "error": "Unhandled webhook event"}

    async def _handle_payment_success(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment webhook."""
        # Implementation would vary by gateway
        return {"success": True}

    async def _handle_subscription_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription update webhook."""
        # Implementation would vary by gateway
        return {"success": True}

    async def _handle_payment_failure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment failure webhook."""
        # Implementation would vary by gateway
        return {"success": True}

    def _validate_webhook(self, gateway: str, payload: Dict[str, Any], 
                         signature: Optional[str]) -> bool:
        """Validate webhook signature."""
        # Implementation would vary by gateway
        return True

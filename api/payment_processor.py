"""
Payment Processing System - Handles invoicing, subscriptions, and payment processing
with support for multiple gateways and automated retry logic.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

class PaymentGateway(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    BRAINTREE = "braintree"

class PaymentStatus(Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"

class PaymentProcessor:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def create_invoice(self, customer_id: str, amount_cents: int, 
                           currency: str = "USD", description: str = "") -> Dict[str, Any]:
        """Create a new invoice for a customer."""
        try:
            invoice_id = str(uuid.uuid4())
            await self.execute_sql(
                f"""
                INSERT INTO invoices (
                    id, customer_id, amount_cents, currency, 
                    description, status, created_at, due_date
                ) VALUES (
                    '{invoice_id}', '{customer_id}', {amount_cents}, 
                    '{currency}', '{description}', 'pending', NOW(), NOW() + INTERVAL '30 days'
                )
                """
            )
            return {"success": True, "invoice_id": invoice_id}
        except Exception as e:
            logger.error(f"Failed to create invoice: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_payment(self, invoice_id: str, gateway: PaymentGateway,
                            payment_method_id: str) -> Dict[str, Any]:
        """Process payment for an invoice through specified gateway."""
        try:
            # Get invoice details
            invoice_res = await self.execute_sql(
                f"SELECT * FROM invoices WHERE id = '{invoice_id}'"
            )
            invoice = invoice_res.get("rows", [{}])[0]
            
            if not invoice:
                return {"success": False, "error": "Invoice not found"}
                
            # Process payment through gateway
            payment_result = await self._charge_payment_gateway(
                gateway, 
                invoice["amount_cents"],
                invoice["currency"],
                payment_method_id
            )
            
            if payment_result["success"]:
                await self._record_successful_payment(invoice_id, payment_result)
                return {"success": True, "payment_id": payment_result["payment_id"]}
            else:
                await self._record_failed_payment(invoice_id, payment_result)
                return {"success": False, "error": payment_result["error"]}
                
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _charge_payment_gateway(self, gateway: PaymentGateway, 
                                    amount_cents: int, currency: str,
                                    payment_method_id: str) -> Dict[str, Any]:
        """Charge payment through the specified gateway."""
        # Implementation would vary per gateway
        # This is a stub implementation
        return {"success": True, "payment_id": str(uuid.uuid4())}

    async def _record_successful_payment(self, invoice_id: str, 
                                        payment_result: Dict[str, Any]) -> None:
        """Record successful payment in database."""
        await self.execute_sql(
            f"""
            UPDATE invoices 
            SET status = 'paid', 
                paid_at = NOW(),
                payment_id = '{payment_result["payment_id"]}'
            WHERE id = '{invoice_id}'
            """
        )

    async def _record_failed_payment(self, invoice_id: str,
                                    payment_result: Dict[str, Any]) -> None:
        """Record failed payment attempt."""
        await self.execute_sql(
            f"""
            UPDATE invoices 
            SET last_payment_attempt = NOW(),
                payment_attempts = payment_attempts + 1,
                last_payment_error = '{payment_result["error"]}'
            WHERE id = '{invoice_id}'
            """
        )

    async def retry_failed_payments(self) -> Dict[str, Any]:
        """Retry failed payments with automatic retry logic."""
        try:
            # Get failed payments that are eligible for retry
            res = await self.execute_sql(
                """
                SELECT * FROM invoices 
                WHERE status = 'failed'
                  AND payment_attempts < 3
                  AND last_payment_attempt < NOW() - INTERVAL '1 day'
                LIMIT 100
                """
            )
            invoices = res.get("rows", [])
            
            succeeded = 0
            failed = 0
            
            for invoice in invoices:
                # Try to charge again
                result = await self.process_payment(
                    invoice["id"],
                    PaymentGateway(invoice["payment_gateway"]),
                    invoice["payment_method_id"]
                )
                
                if result["success"]:
                    succeeded += 1
                else:
                    failed += 1
                    
            return {
                "success": True,
                "retried": len(invoices),
                "succeeded": succeeded,
                "failed": failed
            }
            
        except Exception as e:
            logger.error(f"Failed to retry payments: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_subscription(self, customer_id: str, plan_id: str,
                                payment_method_id: str, gateway: PaymentGateway,
                                trial_days: int = 0) -> Dict[str, Any]:
        """Create a new subscription for a customer."""
        try:
            subscription_id = str(uuid.uuid4())
            
            await self.execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status,
                    payment_method_id, gateway, trial_end,
                    created_at, updated_at
                ) VALUES (
                    '{subscription_id}', '{customer_id}', '{plan_id}', 
                    '{"trialing" if trial_days > 0 else "active"}',
                    '{payment_method_id}', '{gateway.value}',
                    NOW() + INTERVAL '{trial_days} days',
                    NOW(), NOW()
                )
                """
            )
            
            return {"success": True, "subscription_id": subscription_id}
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_subscription_payments(self) -> Dict[str, Any]:
        """Process all due subscription payments."""
        try:
            # Get subscriptions with due payments
            res = await self.execute_sql(
                """
                SELECT * FROM subscriptions
                WHERE status IN ('active', 'trialing')
                  AND next_payment_due <= NOW()
                LIMIT 100
                """
            )
            subscriptions = res.get("rows", [])
            
            succeeded = 0
            failed = 0
            
            for sub in subscriptions:
                # Create invoice
                invoice_result = await self.create_invoice(
                    sub["customer_id"],
                    sub["plan_amount_cents"],
                    sub["plan_currency"]
                )
                
                if not invoice_result["success"]:
                    failed += 1
                    continue
                    
                # Process payment
                payment_result = await self.process_payment(
                    invoice_result["invoice_id"],
                    PaymentGateway(sub["gateway"]),
                    sub["payment_method_id"]
                )
                
                if payment_result["success"]:
                    succeeded += 1
                    await self._update_subscription_after_payment(sub["id"])
                else:
                    failed += 1
                    await self._handle_failed_subscription_payment(sub["id"])
                    
            return {
                "success": True,
                "processed": len(subscriptions),
                "succeeded": succeeded,
                "failed": failed
            }
            
        except Exception as e:
            logger.error(f"Failed to process subscription payments: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _update_subscription_after_payment(self, subscription_id: str) -> None:
        """Update subscription after successful payment."""
        await self.execute_sql(
            f"""
            UPDATE subscriptions
            SET next_payment_due = NOW() + INTERVAL '1 month',
                updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )

    async def _handle_failed_subscription_payment(self, subscription_id: str) -> None:
        """Handle failed subscription payment."""
        await self.execute_sql(
            f"""
            UPDATE subscriptions
            SET status = CASE 
                WHEN payment_attempts >= 2 THEN 'past_due'
                ELSE status
            END,
            payment_attempts = payment_attempts + 1,
            updated_at = NOW()
            WHERE id = '{subscription_id}'
            """
        )

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription."""
        try:
            await self.execute_sql(
                f"""
                UPDATE subscriptions
                SET status = 'canceled',
                    canceled_at = NOW(),
                    updated_at = NOW()
                WHERE id = '{subscription_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {str(e)}")
            return {"success": False, "error": str(e)}

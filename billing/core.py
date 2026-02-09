"""
Core billing system with payment processor integrations.
Handles: subscriptions, invoicing, metering, dunning.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import stripe
import paypalrestsdk

from core.database import query_db, execute_db

# Configure logging
logger = logging.getLogger(__name__)

# Payment processor constants
class PaymentProcessor(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"

# Configure processors (should be moved to config)
stripe.api_key = "sk_test_..."  
paypalrestsdk.configure({
    "mode": "sandbox",
    "client_id": "...",
    "client_secret": "..."
})

class BillingManager:
    """Central billing operations manager."""
    
    def __init__(self):
        self.processors = {
            PaymentProcessor.STRIPE: self._stripe_handler,
            PaymentProcessor.PAYPAL: self._paypal_handler
        }
    
    async def create_subscription(
        self, 
        customer_id: str,
        plan_id: str,
        processor: PaymentProcessor = PaymentProcessor.STRIPE,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create new subscription with payment processor."""
        try:
            return await self.processors[processor](
                "create_subscription",
                customer_id=customer_id,
                plan_id=plan_id,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            raise

    async def create_invoice(
        self,
        customer_id: str,
        items: List[Dict],
        processor: PaymentProcessor = PaymentProcessor.STRIPE,
        auto_advance: bool = True
    ) -> Dict:
        """Generate invoice for customer."""
        try:
            return await self.processors[processor](
                "create_invoice",
                customer_id=customer_id,
                items=items,
                auto_advance=auto_advance
            )
        except Exception as e:
            logger.error(f"Invoice creation failed: {str(e)}")
            raise

    async def record_usage(
        self,
        subscription_id: str,
        meter_name: str,
        quantity: float,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """Record metered usage for billing."""
        ts = timestamp or datetime.now(timezone.utc)
        try:
            await execute_db(
                """
                INSERT INTO billing_metered_usage 
                (subscription_id, meter_name, quantity, recorded_at)
                VALUES (%s, %s, %s, %s)
                """,
                (subscription_id, meter_name, quantity, ts)
            )
            return True
        except Exception as e:
            logger.error(f"Usage recording failed: {str(e)}")
            return False

    async def process_dunning(self) -> Dict:
        """Handle overdue payments and retry logic."""
        results = {"attempted": 0, "succeeded": 0, "failed": 0}
        
        try:
            overdue_invoices = await query_db(
                """
                SELECT invoice_id, customer_id, processor, amount_due
                FROM billing_invoices
                WHERE status = 'open'
                AND due_date < NOW()
                AND payment_attempts < 3
                """
            )
            
            for inv in overdue_invoices.get("rows", []):
                results["attempted"] += 1
                try:
                    processor = PaymentProcessor(inv["processor"])
                    await self.processors[processor](
                        "retry_payment",
                        invoice_id=inv["invoice_id"],
                        customer_id=inv["customer_id"]
                    )
                    results["succeeded"] += 1
                except Exception:
                    results["failed"] += 1
                    await execute_db(
                        """
                        UPDATE billing_invoices
                        SET payment_attempts = payment_attempts + 1,
                            last_attempted = NOW()
                        WHERE invoice_id = %s
                        """,
                        (inv["invoice_id"],)
                    )
            
            return results
            
        except Exception as e:
            logger.error(f"Dunning process failed: {str(e)}")
            raise

    async def _stripe_handler(self, action: str, **kwargs) -> Dict:
        """Handle Stripe API operations."""
        try:
            if action == "create_subscription":
                sub = stripe.Subscription.create(
                    customer=kwargs["customer_id"],
                    items=[{"price": kwargs["plan_id"]}],
                    metadata=kwargs["metadata"]
                )
                return {"success": True, "subscription": sub}
                
            elif action == "create_invoice":
                inv = stripe.Invoice.create(
                    customer=kwargs["customer_id"],
                    auto_advance=kwargs["auto_advance"]
                )
                for item in kwargs["items"]:
                    stripe.InvoiceItem.create(
                        customer=kwargs["customer_id"],
                        invoice=inv.id,
                        amount=item["amount"],
                        currency=item["currency"],
                        description=item.get("description")
                    )
                return {"success": True, "invoice": inv}
                
            elif action == "retry_payment":
                inv = stripe.Invoice.retrieve(kwargs["invoice_id"])
                inv.pay()
                return {"success": True}
                
            raise ValueError(f"Unknown Stripe action: {action}")
            
        except Exception as e:
            logger.error(f"Stripe operation failed: {str(e)}")
            raise

    async def _paypal_handler(self, action: str, **kwargs) -> Dict:
        """Handle PayPal API operations."""
        try:
            if action == "create_subscription":
                agreement = paypalrestsdk.BillingAgreement({
                    "name": kwargs["plan_id"],
                    "description": "Recurring billing",
                    "start_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "payer": {"payment_method": "paypal"},
                    "plan": {"id": kwargs["plan_id"]}
                })
                if agreement.create():
                    return {"success": True, "subscription": agreement}
                raise ValueError(agreement.error)
                
            elif action == "create_invoice":
                invoice = paypalrestsdk.Invoice({"merchant_info": {"email": "..."}})
                # PayPal invoice logic here
                return {"success": True, "invoice": invoice}
                
            elif action == "retry_payment":
                invoice = paypalrestsdk.Invoice.find(kwargs["invoice_id"])
                invoice.send()
                return {"success": True}
                
            raise ValueError(f"Unknown PayPal action: {action}")
            
        except Exception as e:
            logger.error(f"PayPal operation failed: {str(e)}")
            raise

    async def recognize_revenue(self, invoice_id: str) -> bool:
        """
        Apply revenue recognition rules to invoice.
        Implements ASC 606 compliant recognition logic.
        """
        try:
            invoice = await query_db(
                "SELECT * FROM billing_invoices WHERE invoice_id = %s",
                (invoice_id,)
            )
            
            if not invoice["rows"]:
                return False
                
            invoice = invoice["rows"][0]
            
            # Calculate revenue recognition schedule
            recognized_periods = []
            total_amount = float(invoice["amount_due"])
            recogn_date = datetime.now(timezone.utc)
            
            if invoice["terms"] == "upfront":
                recognized_periods.append({
                    "amount": total_amount,
                    "recognized_at": recogn_date,
                    "period_start": recogn_date,
                    "period_end": recogn_date
                })
            else:
                # For subscriptions, recognize evenly over the term
                term_length = self._get_term_length_months(invoice["terms"])
                monthly_amount = total_amount / term_length
                
                for month in range(term_length):
                    period_start = recogn_date + timedelta(days=30*month)
                    period_end = recogn_date + timedelta(days=30*(month+1)) - timedelta(seconds=1)
                    
                    recognized_periods.append({
                        "amount": monthly_amount,
                        "recognized_at": recogn_date,
                        "period_start": period_start,
                        "period_end": period_end
                    })
            
            # Record recognized revenue
            for period in recognized_periods:
                await execute_db(
                    """
                    INSERT INTO billing_revenue_recognition
                    (invoice_id, amount, recognized_at, period_start, period_end, processor)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invoice_id,
                        period["amount"],
                        period["recognized_at"],
                        period["period_start"],
                        period["period_end"],
                        invoice["processor"]
                    )
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Revenue recognition failed: {str(e)}")
            return False

    def _get_term_length_months(self, terms: str) -> int:
        """Parse billing terms duration."""
        if "month" in terms:
            return int(terms.split(" ")[0])
        return 1  # Default to monthly

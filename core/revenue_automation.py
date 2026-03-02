from __future__ import annotations
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from core.database import query_db
from core.payment_processor import PaymentProcessor

class RevenueAutomation:
    """Automates revenue generation workflows."""
    
    BASE_PRODUCT_PRICE = Decimal('99.00')
    SCALE_THRESHOLD = Decimal('10000.00')  # $10K/month
    
    def __init__(self, stripe_key: str, execute_sql: Callable, log_action: Callable):
        self.processor = PaymentProcessor(stripe_key)
        self.execute_sql = execute_sql
        self.log = log_action
        self.logger = logging.getLogger(__name__)
        
    async def process_new_customers(self, batch_size: int = 20) -> Dict[str, Any]:
        """Process new customer signups for revenue conversion."""
        try:
            res = await query_db(f"""
                SELECT id, email, name, signup_date 
                FROM customers 
                WHERE payment_status = 'pending'
                LIMIT {batch_size}
            """)
            customers = res.get("rows", [])
            
            processed = 0
            revenue_cents = 0
            
            for cust in customers:
                email = cust.get("email", "")
                if not email:
                    continue
                    
                # Create customer in Stripe
                cust_data = {
                    "name": cust.get("name"),
                    "signup_source": "web",
                    "internal_id": cust.get("id")
                }
                result = self.processor.create_customer(email, **cust_data)
                
                if not result.get("success"):
                    await self._log_failure(cust.get("id"), result.get("error"))
                    continue
                    
                # Attempt initial charge
                charge_result = self.processor.record_charge(
                    amount=self.BASE_PRODUCT_PRICE,
                    description="Initial purchase",
                    metadata={
                        "customer_id": cust.get("id"),
                        "type": "onboarding"
                    }
                )
                
                if charge_result.get("success"):
                    await self._record_successful_payment(
                        cust.get("id"),
                        charge_result["charge_id"],
                        charge_result["amount_cents"],
                        "initial"
                    )
                    processed += 1
                    revenue_cents += charge_result["amount_cents"]
            
            return {
                "success": True,
                "processed": processed,
                "revenue_cents": revenue_cents
            }
            
        except Exception as e:
            self.logger.error(f"Customer processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _record_successful_payment(
        self,
        customer_id: str,
        charge_id: str,
        amount_cents: int,
        payment_type: str
    ) -> None:
        """Record successful payment in database."""
        try:
            await self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, experiment_id, event_type, 
                    amount_cents, recorded_at
                ) VALUES (
                    gen_random_uuid(),
                    NULL,
                    'revenue',
                    {amount_cents},
                    NOW()
                )
            """)
            
            await self.execute_sql(f"""
                UPDATE customers
                SET payment_status = 'active',
                    last_payment_at = NOW(),
                    stripe_charge_id = '{charge_id}'
                WHERE id = '{customer_id}'
            """)
            
            self.log(f"payment.{payment_type}.success", 
                   f"Successful {payment_type} payment processed",
                   level="info",
                   data={
                       "customer_id": customer_id,
                       "amount_cents": amount_cents
                   })
                   
        except Exception as e:
            self.logger.error(f"Failed to record payment: {str(e)}")
    
    async def _log_failure(self, customer_id: str, error: str) -> None:
        """Handle payment processing failures."""
        try:
            await self.execute_sql(f"""
                UPDATE customers
                SET payment_status = 'failed',
                    last_failed_at = NOW()
                WHERE id = '{customer_id}'
            """)
            
            self.log("payment.failed",
                   f"Payment processing failed: {error}",
                   level="error",
                   data={
                       "customer_id": customer_id,
                       "error": error
                   })
                   
        except Exception as e:
            self.logger.error(f"Failed to log failure: {str(e)}")

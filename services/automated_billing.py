"""
Automated billing and service delivery system with circuit breakers.
Handles payment processing, service delivery, and error recovery.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import random
import json
import logging

from core.database import query_db, execute_sql
from core.circuit_breaker import CircuitBreaker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        self.delivery_service = DeliveryService()
        self.circuit_breaker = CircuitBreaker(
            max_failures=5,
            reset_timeout=300  # 5 minutes
        )

    async def process_subscription(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """
        End-to-end subscription processing with circuit breakers and error handling.
        """
        if self.circuit_breaker.is_open():
            return {
                "success": False,
                "error": "Service temporarily unavailable due to high error rate",
                "circuit_state": "open"
            }

        try:
            # Step 1: Validate inputs
            if not customer_id or not plan_id:
                raise ValueError("Missing required parameters")

            # Step 2: Process payment
            payment_result = await self.payment_processor.charge_customer(customer_id, plan_id)
            if not payment_result.get("success"):
                self.circuit_breaker.record_failure()
                return payment_result

            # Step 3: Deliver service
            delivery_result = await self.delivery_service.provision_service(
                customer_id, 
                plan_id,
                payment_result["transaction_id"]
            )
            if not delivery_result.get("success"):
                # Initiate refund if delivery fails
                await self.payment_processor.issue_refund(
                    payment_result["transaction_id"],
                    reason="Service delivery failed"
                )
                self.circuit_breaker.record_failure()
                return delivery_result

            # Record successful transaction
            await self._record_transaction(
                customer_id=customer_id,
                plan_id=plan_id,
                amount=payment_result["amount"],
                transaction_id=payment_result["transaction_id"],
                service_delivery_id=delivery_result["delivery_id"]
            )

            self.circuit_breaker.record_success()
            return {
                "success": True,
                "transaction_id": payment_result["transaction_id"],
                "delivery_id": delivery_result["delivery_id"],
                "amount": payment_result["amount"]
            }

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Subscription processing failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "circuit_state": self.circuit_breaker.state
            }

    async def _record_transaction(self, **kwargs) -> None:
        """Record successful transaction in database."""
        try:
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    customer_id, plan_id, transaction_id, service_delivery_id,
                    recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(), 'revenue', {int(kwargs['amount'] * 100)}, 'USD',
                    'automated_billing', '{kwargs['customer_id']}', '{kwargs['plan_id']}',
                    '{kwargs['transaction_id']}', '{kwargs['service_delivery_id']}',
                    NOW(), NOW()
                )
                """
            )
        except Exception as e:
            logger.error(f"Failed to record transaction: {str(e)}")


class PaymentProcessor:
    """Mock payment processor with retry logic"""
    
    async def charge_customer(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Process payment with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # In a real implementation, this would call a payment provider API
                amount = self._get_plan_amount(plan_id)
                if random.random() < 0.05:  # Simulate 5% failure rate
                    raise Exception("Payment processor timeout")
                
                return {
                    "success": True,
                    "transaction_id": f"txn_{int(time.time())}_{customer_id[:8]}",
                    "amount": amount,
                    "currency": "USD"
                }
            except Exception as e:
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Payment failed after {max_retries} attempts: {str(e)}"
                    }
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

    async def issue_refund(self, transaction_id: str, reason: str = "") -> Dict[str, Any]:
        """Process refund"""
        try:
            # Record refund as a negative revenue event
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    transaction_id, refund_reason, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(), 'refund', -1000, 'USD',
                    'automated_billing', '{transaction_id}', '{reason}',
                    NOW(), NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_plan_amount(self, plan_id: str) -> float:
        """Get plan pricing"""
        plans = {
            "basic": 9.99,
            "pro": 29.99,
            "enterprise": 99.99
        }
        return plans.get(plan_id, 9.99)


class DeliveryService:
    """Service delivery with validation and retries"""
    
    async def provision_service(self, customer_id: str, plan_id: str, transaction_id: str) -> Dict[str, Any]:
        """Deliver purchased service"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Simulate service provisioning
                if random.random() < 0.03:  # 3% failure rate
                    raise Exception("Service provisioning failed")
                
                return {
                    "success": True,
                    "delivery_id": f"dlv_{int(time.time())}_{customer_id[:8]}",
                    "plan_id": plan_id,
                    "provisioned_at": datetime.utcnow().isoformat()
                }
            except Exception as e:
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Service delivery failed after {max_retries} attempts: {str(e)}"
                    }
                await asyncio.sleep(0.5 * (attempt + 1))

from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from circuitbreaker import circuit

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handle payment processing with retries and circuit breakers"""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        self.max_retries = 3
        self.circuit_timeout = 60  # seconds
        
    @circuit(failure_threshold=3, recovery_timeout=self.circuit_timeout)
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment with retries and circuit breaker"""
        try:
            # Insert payment record
            result = await self.execute_sql(
                f"""
                INSERT INTO payments (
                    id, amount_cents, currency, status,
                    payment_method, customer_id, metadata,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    {payment_data['amount_cents']},
                    '{payment_data['currency']}',
                    'pending',
                    '{payment_data['payment_method']}',
                    '{payment_data['customer_id']}',
                    '{json.dumps(payment_data.get('metadata', {}))}'::jsonb,
                    NOW(),
                    NOW()
                )
                RETURNING id
                """
            )
            return {"success": True, "payment_id": result["rows"][0]["id"]}
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            raise

class ServiceDelivery:
    """Handle automated service delivery with retry logic"""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def deliver_service(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver service with retries"""
        try:
            # Mark service as delivered
            result = await self.execute_sql(
                f"""
                UPDATE services
                SET status = 'delivered',
                    delivered_at = NOW()
                WHERE id = '{service_data['service_id']}'
                RETURNING id
                """
            )
            return {"success": True, "service_id": result["rows"][0]["id"]}
        except Exception as e:
            logger.error(f"Service delivery failed: {str(e)}")
            raise

class RevenueSystem:
    """Core autonomous revenue system"""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.payment_processor = PaymentProcessor(execute_sql)
        self.service_delivery = ServiceDelivery(execute_sql)
        
    async def process_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process complete transaction flow"""
        try:
            # Step 1: Process payment
            payment_result = await self.payment_processor.process_payment({
                "amount_cents": transaction_data["amount_cents"],
                "currency": transaction_data["currency"],
                "payment_method": transaction_data["payment_method"],
                "customer_id": transaction_data["customer_id"],
                "metadata": transaction_data.get("metadata", {})
            })
            
            # Step 2: Deliver service
            service_result = await self.service_delivery.deliver_service({
                "service_id": transaction_data["service_id"]
            })
            
            # Step 3: Record revenue event
            await self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, amount_cents, currency, event_type,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    {transaction_data['amount_cents']},
                    '{transaction_data['currency']}',
                    'revenue',
                    '{transaction_data['source']}',
                    '{json.dumps(transaction_data.get('metadata', {}))}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            
            return {"success": True, "payment_id": payment_result["payment_id"], "service_id": service_result["service_id"]}
            
        except Exception as e:
            logger.error(f"Transaction processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def recover_failed_transactions(self) -> Dict[str, Any]:
        """Recover failed transactions"""
        try:
            # Get failed transactions
            result = await self.execute_sql(
                """
                SELECT * FROM transactions
                WHERE status = 'failed'
                AND created_at >= NOW() - INTERVAL '1 hour'
                LIMIT 100
                """
            )
            
            recovered = 0
            for transaction in result.get("rows", []):
                recovery_result = await self.process_transaction(transaction)
                if recovery_result["success"]:
                    recovered += 1
                    await self.execute_sql(
                        f"""
                        UPDATE transactions
                        SET status = 'recovered'
                        WHERE id = '{transaction['id']}'
                        """
                    )
                    
            return {"success": True, "recovered": recovered}
            
        except Exception as e:
            logger.error(f"Transaction recovery failed: {str(e)}")
            return {"success": False, "error": str(e)}

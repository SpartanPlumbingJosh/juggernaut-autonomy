"""
Autonomous Revenue Generation Service
Handles automated product delivery and payment processing.
"""

import asyncio
from datetime import datetime, timedelta
import logging
import random
import time
from typing import Dict, Optional

from core.database import query_db, execute_db
from core.payment_processor import PaymentProcessor
from core.delivery_engine import DeliveryEngine

class AutonomousRevenueService:
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        self.delivery_engine = DeliveryEngine()
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
    async def process_order(self, order_data: Dict) -> Dict:
        """
        Fully automated order processing pipeline.
        
        Steps:
        1. Validate order
        2. Process payment
        3. Deliver product
        4. Record transaction
        5. Handle errors and retries
        """
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            try:
                # Step 1: Validate
                if not self._validate_order(order_data):
                    return {"success": False, "error": "Invalid order data"}
                
                # Step 2: Payment
                payment_result = await self.payment_processor.charge(
                    amount=order_data['amount'],
                    currency=order_data['currency'],
                    payment_method=order_data['payment_method']
                )
                if not payment_result['success']:
                    return payment_result
                
                # Step 3: Delivery
                delivery_result = await self.delivery_engine.fulfill(
                    product_id=order_data['product_id'],
                    customer=order_data['customer']
                )
                if not delivery_result['success']:
                    await self.payment_processor.refund(payment_result['transaction_id'])
                    return delivery_result
                
                # Step 4: Record
                transaction = await self._record_transaction(
                    order_data=order_data,
                    payment_data=payment_result,
                    delivery_data=delivery_result
                )
                
                return {
                    "success": True,
                    "transaction_id": transaction['id'],
                    "payment_status": "completed",
                    "delivery_status": "fulfilled"
                }
                
            except Exception as e:
                last_error = str(e)
                attempts += 1
                logging.error(f"Order processing attempt {attempts} failed: {last_error}")
                if attempts < self.max_retries:
                    time.sleep(self.retry_delay * attempts)  # Exponential backoff
                    
        return {
            "success": False,
            "error": f"Failed after {attempts} attempts",
            "last_error": last_error
        }

    def _validate_order(self, order_data: Dict) -> bool:
        """Validate order parameters"""
        required_fields = {'amount', 'currency', 'product_id', 'customer', 'payment_method'}
        return all(field in order_data for field in required_fields)
        
    async def _record_transaction(self, order_data: Dict, payment_data: Dict, delivery_data: Dict) -> Dict:
        """Record successful transaction in database"""
        transaction_data = {
            'order_data': order_data,
            'payment_data': payment_data,
            'delivery_data': delivery_data,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'completed'
        }
        
        result = await execute_db(
            """
            INSERT INTO transactions (
                id, 
                data,
                created_at,
                updated_at
            ) VALUES (
                gen_random_uuid(),
                %s::jsonb,
                NOW(),
                NOW()
            )
            RETURNING *
            """,
            (json.dumps(transaction_data),)
        )
        
        return result['rows'][0]

    async def check_system_health(self) -> Dict:
        """Verify all components are operational"""
        checks = {
            'payment_service': await self.payment_processor.check_health(),
            'delivery_service': await self.delivery_engine.check_health(),
            'database': await self._check_db_connection()
        }
        
        healthy = all(check['healthy'] for check in checks.values())
        return {
            'healthy': healthy,
            'checks': checks
        }

    async def _check_db_connection(self) -> Dict:
        try:
            await query_db("SELECT 1")
            return {'healthy': True}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}

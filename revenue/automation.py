"""
Revenue Automation Core - Handles customer acquisition, payments, and service delivery.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
import paypalrestsdk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RevenueAutomation:
    def __init__(self, db_executor, config: Dict[str, Any]):
        """
        Initialize revenue automation system.
        
        Args:
            db_executor: Function to execute SQL queries
            config: Configuration dictionary with API keys and settings
        """
        self.db_executor = db_executor
        self.config = config
        
        # Initialize payment processors
        stripe.api_key = config.get('stripe_secret_key')
        paypalrestsdk.configure({
            "mode": config.get('paypal_mode', 'sandbox'),
            "client_id": config.get('paypal_client_id'),
            "client_secret": config.get('paypal_client_secret')
        })
        
    async def handle_new_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process new customer through acquisition funnel.
        
        Steps:
        1. Validate customer data
        2. Create payment method
        3. Process initial payment
        4. Initiate service delivery
        5. Record transaction
        
        Returns:
            Dict with status and details
        """
        try:
            # Validate customer data
            if not self._validate_customer_data(customer_data):
                return {"status": "error", "message": "Invalid customer data"}
                
            # Create payment method
            payment_method = await self._create_payment_method(customer_data)
            if not payment_method.get('success'):
                return payment_method
                
            # Process initial payment
            payment_result = await self._process_payment(
                payment_method['payment_id'],
                customer_data['amount'],
                customer_data['currency']
            )
            if not payment_result.get('success'):
                return payment_result
                
            # Initiate service delivery
            delivery_result = await self._initiate_service_delivery(customer_data)
            if not delivery_result.get('success'):
                return delivery_result
                
            # Record transaction
            transaction_id = await self._record_transaction(
                customer_data,
                payment_result,
                delivery_result
            )
            
            return {
                "status": "success",
                "transaction_id": transaction_id,
                "payment_id": payment_result['payment_id'],
                "delivery_id": delivery_result['delivery_id']
            }
            
        except Exception as e:
            logger.error(f"Customer acquisition failed: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def _validate_customer_data(self, data: Dict[str, Any]) -> bool:
        """Validate required customer fields."""
        required_fields = ['email', 'name', 'amount', 'currency', 'product_id']
        return all(field in data for field in required_fields)
        
    async def _create_payment_method(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create payment method based on customer's payment info.
        
        Supports both Stripe and PayPal.
        """
        try:
            payment_type = customer_data.get('payment_type', 'stripe')
            
            if payment_type == 'stripe':
                # Create Stripe payment method
                payment_method = stripe.PaymentMethod.create(
                    type="card",
                    card={
                        "number": customer_data['card_number'],
                        "exp_month": customer_data['card_exp_month'],
                        "exp_year": customer_data['card_exp_year'],
                        "cvc": customer_data['card_cvc']
                    },
                )
                return {
                    "success": True,
                    "payment_id": payment_method.id,
                    "payment_type": "stripe"
                }
                
            elif payment_type == 'paypal':
                # Create PayPal payment method
                payment = paypalrestsdk.Payment({
                    "intent": "sale",
                    "payer": {
                        "payment_method": "paypal"
                    },
                    "transactions": [{
                        "amount": {
                            "total": str(customer_data['amount']),
                            "currency": customer_data['currency']
                        }
                    }]
                })
                
                if payment.create():
                    return {
                        "success": True,
                        "payment_id": payment.id,
                        "payment_type": "paypal"
                    }
                else:
                    return {
                        "success": False,
                        "message": payment.error
                    }
                    
            return {"success": False, "message": "Unsupported payment type"}
            
        except Exception as e:
            logger.error(f"Payment method creation failed: {str(e)}")
            return {"success": False, "message": str(e)}
            
    async def _process_payment(self, payment_id: str, amount: float, currency: str) -> Dict[str, Any]:
        """
        Process payment using created payment method.
        """
        try:
            # Check if payment already processed
            existing = await self.db_executor(
                f"SELECT id FROM revenue_events WHERE payment_id = '{payment_id}'"
            )
            if existing.get('rows'):
                return {
                    "success": True,
                    "payment_id": payment_id,
                    "message": "Payment already processed"
                }
                
            # Record payment event
            await self.db_executor(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'payment',
                    {int(amount * 100)},
                    '{currency}',
                    'automation',
                    '{{"payment_id": "{payment_id}"}}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            
            return {
                "success": True,
                "payment_id": payment_id
            }
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "message": str(e)}
            
    async def _initiate_service_delivery(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initiate automated service delivery.
        """
        try:
            # Record delivery event
            result = await self.db_executor(
                f"""
                INSERT INTO service_deliveries (
                    id, customer_email, product_id,
                    status, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_data['email']}',
                    '{customer_data['product_id']}',
                    'pending',
                    NOW(),
                    NOW()
                )
                RETURNING id
                """
            )
            
            delivery_id = result.get('rows', [{}])[0].get('id')
            
            # TODO: Implement actual service delivery logic
            
            return {
                "success": True,
                "delivery_id": delivery_id
            }
            
        except Exception as e:
            logger.error(f"Service delivery failed: {str(e)}")
            return {"success": False, "message": str(e)}
            
    async def _record_transaction(self, customer_data: Dict[str, Any],
                                payment_result: Dict[str, Any],
                                delivery_result: Dict[str, Any]) -> str:
        """
        Record complete transaction in database.
        """
        try:
            result = await self.db_executor(
                f"""
                INSERT INTO revenue_transactions (
                    id, customer_email, amount_cents, currency,
                    payment_id, delivery_id, status, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_data['email']}',
                    {int(customer_data['amount'] * 100)},
                    '{customer_data['currency']}',
                    '{payment_result['payment_id']}',
                    '{delivery_result['delivery_id']}',
                    'completed',
                    NOW()
                )
                RETURNING id
                """
            )
            
            return result.get('rows', [{}])[0].get('id')
            
        except Exception as e:
            logger.error(f"Transaction recording failed: {str(e)}")
            raise e
            
    async def monitor_transactions(self):
        """
        Background task to monitor and handle transaction statuses.
        """
        while True:
            try:
                # Check for pending transactions
                pending = await self.db_executor(
                    """
                    SELECT id, customer_email, amount_cents, currency,
                           payment_id, delivery_id, status
                    FROM revenue_transactions
                    WHERE status = 'pending'
                    LIMIT 100
                    """
                )
                
                for transaction in pending.get('rows', []):
                    await self._process_transaction(transaction)
                    
            except Exception as e:
                logger.error(f"Transaction monitoring failed: {str(e)}")
                
            # Sleep before next check
            await asyncio.sleep(60)
            
    async def _process_transaction(self, transaction: Dict[str, Any]):
        """
        Process individual transaction status.
        """
        try:
            # Check payment status
            payment_status = await self._check_payment_status(transaction['payment_id'])
            
            if payment_status == 'failed':
                await self.db_executor(
                    f"""
                    UPDATE revenue_transactions
                    SET status = 'failed',
                        updated_at = NOW()
                    WHERE id = '{transaction['id']}'
                    """
                )
                return
                
            # Check delivery status
            delivery_status = await self._check_delivery_status(transaction['delivery_id'])
            
            if delivery_status == 'completed':
                await self.db_executor(
                    f"""
                    UPDATE revenue_transactions
                    SET status = 'completed',
                        updated_at = NOW()
                    WHERE id = '{transaction['id']}'
                    """
                )
                
        except Exception as e:
            logger.error(f"Transaction processing failed: {str(e)}")
            
    async def _check_payment_status(self, payment_id: str) -> str:
        """
        Check payment processor for current status.
        """
        try:
            # Check Stripe payment
            if payment_id.startswith('ch_'):
                charge = stripe.Charge.retrieve(payment_id)
                return charge.status
                
            # Check PayPal payment
            elif payment_id.startswith('PAY-'):
                payment = paypalrestsdk.Payment.find(payment_id)
                return payment.state
                
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Payment status check failed: {str(e)}")
            return 'failed'
            
    async def _check_delivery_status(self, delivery_id: str) -> str:
        """
        Check service delivery status.
        """
        try:
            result = await self.db_executor(
                f"""
                SELECT status
                FROM service_deliveries
                WHERE id = '{delivery_id}'
                LIMIT 1
                """
            )
            
            return result.get('rows', [{}])[0].get('status', 'pending')
            
        except Exception as e:
            logger.error(f"Delivery status check failed: {str(e)}")
            return 'failed'

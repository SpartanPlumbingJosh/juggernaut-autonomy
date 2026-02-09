"""
Core Revenue Engine - Handles automated payment processing, customer onboarding,
service delivery, and revenue recognition.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class RevenueEngine:
    def __init__(self, db_executor, payment_gateway, notification_service):
        self.db_executor = db_executor
        self.payment_gateway = payment_gateway
        self.notification_service = notification_service
        
    async def onboard_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle customer onboarding process"""
        try:
            # Validate required fields
            required_fields = ['email', 'name', 'payment_method']
            if not all(field in customer_data for field in required_fields):
                return {"success": False, "error": "Missing required fields"}
                
            # Create customer record
            customer_id = await self._create_customer_record(customer_data)
            
            # Setup payment method
            payment_result = await self.payment_gateway.create_customer(
                customer_id,
                customer_data['payment_method']
            )
            
            if not payment_result.get('success'):
                return {"success": False, "error": "Payment setup failed"}
                
            # Send welcome email
            await self.notification_service.send_welcome_email(
                customer_data['email'],
                customer_data['name']
            )
            
            return {"success": True, "customer_id": customer_id}
            
        except Exception as e:
            logger.error(f"Onboarding failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def process_payment(self, customer_id: str, amount: float, currency: str) -> Dict[str, Any]:
        """Process payment transaction"""
        try:
            # Validate customer
            customer = await self._get_customer(customer_id)
            if not customer:
                return {"success": False, "error": "Customer not found"}
                
            # Process payment
            payment_result = await self.payment_gateway.charge(
                customer_id,
                amount,
                currency
            )
            
            if not payment_result.get('success'):
                return {"success": False, "error": "Payment failed"}
                
            # Record revenue event
            await self._record_revenue_event(
                customer_id,
                amount,
                currency,
                "payment",
                payment_result
            )
            
            return {"success": True, "transaction_id": payment_result['transaction_id']}
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def deliver_service(self, customer_id: str, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle service delivery"""
        try:
            # Validate customer
            customer = await self._get_customer(customer_id)
            if not customer:
                return {"success": False, "error": "Customer not found"}
                
            # Record service delivery
            delivery_id = await self._record_service_delivery(customer_id, service_data)
            
            # Send delivery confirmation
            await self.notification_service.send_delivery_confirmation(
                customer['email'],
                service_data
            )
            
            return {"success": True, "delivery_id": delivery_id}
            
        except Exception as e:
            logger.error(f"Service delivery failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _create_customer_record(self, customer_data: Dict[str, Any]) -> str:
        """Create customer record in database"""
        sql = """
            INSERT INTO customers (id, email, name, metadata, created_at)
            VALUES (gen_random_uuid(), %s, %s, %s, NOW())
            RETURNING id
        """
        result = await self.db_executor(sql, [
            customer_data['email'],
            customer_data['name'],
            json.dumps(customer_data.get('metadata', {}))
        ])
        return result['rows'][0]['id']
        
    async def _get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer record"""
        sql = "SELECT * FROM customers WHERE id = %s"
        result = await self.db_executor(sql, [customer_id])
        return result['rows'][0] if result['rows'] else None
        
    async def _record_revenue_event(self, customer_id: str, amount: float, currency: str,
                                  event_type: str, metadata: Dict[str, Any]) -> str:
        """Record revenue event"""
        sql = """
            INSERT INTO revenue_events (
                id, customer_id, amount_cents, currency, event_type,
                metadata, recorded_at, created_at
            )
            VALUES (
                gen_random_uuid(), %s, %s, %s, %s, %s, NOW(), NOW()
            )
            RETURNING id
        """
        result = await self.db_executor(sql, [
            customer_id,
            int(amount * 100),  # Convert to cents
            currency,
            event_type,
            json.dumps(metadata)
        ])
        return result['rows'][0]['id']
        
    async def _record_service_delivery(self, customer_id: str, service_data: Dict[str, Any]) -> str:
        """Record service delivery"""
        sql = """
            INSERT INTO service_deliveries (
                id, customer_id, service_type, details, delivered_at, created_at
            )
            VALUES (
                gen_random_uuid(), %s, %s, %s, NOW(), NOW()
            )
            RETURNING id
        """
        result = await self.db_executor(sql, [
            customer_id,
            service_data['service_type'],
            json.dumps(service_data.get('details', {}))
        ])
        return result['rows'][0]['id']

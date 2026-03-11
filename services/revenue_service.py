"""
Revenue Service - Core business logic for automated service delivery and payment processing.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from core.database import query_db

logger = logging.getLogger(__name__)

class RevenueService:
    """Core revenue generation service."""
    
    def __init__(self, payment_gateway):
        self.payment_gateway = payment_gateway
        
    async def deliver_service(self, service_data: Dict) -> Dict:
        """
        Deliver service and process payment.
        
        Args:
            service_data: Dictionary containing service details and payment info
            
        Returns:
            Dictionary with success status and transaction details
        """
        try:
            # Validate service data
            if not self._validate_service_data(service_data):
                return {"success": False, "error": "Invalid service data"}
                
            # Process payment
            payment_result = await self.payment_gateway.process_payment(
                amount=service_data["amount"],
                currency=service_data["currency"],
                payment_method=service_data["payment_method"]
            )
            
            if not payment_result.get("success"):
                return {"success": False, "error": "Payment failed"}
                
            # Record revenue event
            revenue_event = {
                "event_type": "revenue",
                "amount_cents": int(service_data["amount"] * 100),
                "currency": service_data["currency"],
                "source": service_data.get("source", "direct"),
                "metadata": {
                    "service_type": service_data["service_type"],
                    "customer_id": service_data.get("customer_id"),
                    "payment_id": payment_result["payment_id"]
                },
                "recorded_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self._record_revenue_event(revenue_event)
            
            return {
                "success": True,
                "transaction_id": payment_result["payment_id"],
                "amount": service_data["amount"],
                "currency": service_data["currency"]
            }
            
        except Exception as e:
            logger.error(f"Service delivery failed: {str(e)}")
            return {"success": False, "error": "Service delivery failed"}
            
    def _validate_service_data(self, service_data: Dict) -> bool:
        """Validate required service data fields."""
        required_fields = ["amount", "currency", "payment_method", "service_type"]
        return all(field in service_data for field in required_fields)
        
    async def _record_revenue_event(self, event_data: Dict) -> None:
        """Record revenue event to database."""
        sql = """
        INSERT INTO revenue_events (
            id, event_type, amount_cents, currency, source, metadata, recorded_at
        ) VALUES (
            gen_random_uuid(),
            %(event_type)s,
            %(amount_cents)s,
            %(currency)s,
            %(source)s,
            %(metadata)s,
            %(recorded_at)s
        )
        """
        await query_db(sql, event_data)
        
    async def refund_transaction(self, transaction_id: str) -> Dict:
        """
        Process refund for a transaction.
        
        Args:
            transaction_id: Original transaction ID to refund
            
        Returns:
            Dictionary with success status and refund details
        """
        try:
            # Get original transaction
            sql = """
            SELECT * FROM revenue_events
            WHERE metadata->>'payment_id' = %s
            LIMIT 1
            """
            result = await query_db(sql, {"transaction_id": transaction_id})
            original_tx = result.get("rows", [{}])[0]
            
            if not original_tx:
                return {"success": False, "error": "Transaction not found"}
                
            # Process refund
            refund_result = await self.payment_gateway.process_refund(
                amount=original_tx["amount_cents"] / 100,
                currency=original_tx["currency"],
                original_transaction_id=transaction_id
            )
            
            if not refund_result.get("success"):
                return {"success": False, "error": "Refund failed"}
                
            # Record refund event
            refund_event = {
                "event_type": "refund",
                "amount_cents": original_tx["amount_cents"],
                "currency": original_tx["currency"],
                "source": original_tx["source"],
                "metadata": {
                    "original_transaction_id": transaction_id,
                    "refund_id": refund_result["refund_id"]
                },
                "recorded_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self._record_revenue_event(refund_event)
            
            return {
                "success": True,
                "refund_id": refund_result["refund_id"],
                "amount": original_tx["amount_cents"] / 100,
                "currency": original_tx["currency"]
            }
            
        except Exception as e:
            logger.error(f"Refund failed: {str(e)}")
            return {"success": False, "error": "Refund processing failed"}

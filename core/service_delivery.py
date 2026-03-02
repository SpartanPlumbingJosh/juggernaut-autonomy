from datetime import datetime, timezone
from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

class ServiceDelivery:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def deliver_service(self, order_id: str) -> Dict[str, Any]:
        """Automatically deliver a service based on order details."""
        try:
            # Get order details
            res = await self.execute_sql(f"""
                SELECT * FROM orders WHERE id = '{order_id}'
            """)
            order = res.get("rows", [{}])[0]
            
            if not order:
                return {"success": False, "error": "Order not found"}
                
            # Process delivery based on service type
            service_type = order.get("service_type")
            metadata = order.get("metadata", {})
            
            if service_type == "digital":
                # Generate digital access credentials
                access_token = self._generate_access_token()
                await self.execute_sql(f"""
                    UPDATE orders 
                    SET status = 'delivered',
                        delivery_metadata = '{json.dumps({"access_token": access_token})}'::jsonb
                    WHERE id = '{order_id}'
                """)
                
            elif service_type == "physical":
                # Trigger shipping process
                await self.execute_sql(f"""
                    UPDATE orders 
                    SET status = 'shipped',
                        delivery_metadata = '{json.dumps({"tracking_number": self._generate_tracking_number()})}'::jsonb
                    WHERE id = '{order_id}'
                """)
                
            return {"success": True, "order_id": order_id}
            
        except Exception as e:
            logger.error(f"Service delivery failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def _generate_access_token(self) -> str:
        """Generate a secure access token."""
        import secrets
        return secrets.token_urlsafe(32)
        
    def _generate_tracking_number(self) -> str:
        """Generate a tracking number."""
        import uuid
        return str(uuid.uuid4()).replace("-", "")[:16].upper()

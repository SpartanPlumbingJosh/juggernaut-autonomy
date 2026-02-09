from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

class RevenueStream:
    """Manage a primary revenue stream with automation and tracking."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def create_stream(self, name: str, price_cents: int, delivery_type: str) -> Dict[str, Any]:
        """Create a new revenue stream."""
        stream_id = str(uuid.uuid4())
        try:
            self.execute_sql(f"""
                INSERT INTO revenue_streams (
                    id, name, price_cents, delivery_type,
                    status, created_at, updated_at
                ) VALUES (
                    '{stream_id}',
                    '{name.replace("'", "''")}',
                    {price_cents},
                    '{delivery_type.replace("'", "''")}',
                    'active',
                    NOW(),
                    NOW()
                )
            """)
            return {"success": True, "stream_id": stream_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def process_payment(self, stream_id: str, user_id: str, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a payment for the revenue stream."""
        try:
            # Record payment
            payment_id = str(uuid.uuid4())
            self.execute_sql(f"""
                INSERT INTO revenue_payments (
                    id, stream_id, user_id, amount_cents,
                    status, created_at, updated_at
                ) VALUES (
                    '{payment_id}',
                    '{stream_id}',
                    '{user_id}',
                    {payment_data['amount_cents']},
                    'completed',
                    NOW(),
                    NOW()
                )
            """)
            
            # Trigger delivery
            self._trigger_delivery(stream_id, user_id)
            
            return {"success": True, "payment_id": payment_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _trigger_delivery(self, stream_id: str, user_id: str) -> None:
        """Trigger automated delivery of the product/service."""
        try:
            # Get stream details
            res = self.execute_sql(f"""
                SELECT delivery_type FROM revenue_streams
                WHERE id = '{stream_id}'
            """)
            delivery_type = res.get("rows", [{}])[0].get("delivery_type")
            
            # Handle different delivery types
            if delivery_type == "digital":
                self._deliver_digital_product(user_id)
            elif delivery_type == "service":
                self._schedule_service(user_id)
                
        except Exception as e:
            self.log_action("revenue.delivery_failed", 
                          f"Failed to trigger delivery: {str(e)}",
                          level="error")
            
    def _deliver_digital_product(self, user_id: str) -> None:
        """Deliver a digital product."""
        # Implementation would depend on the specific product
        pass
        
    def _schedule_service(self, user_id: str) -> None:
        """Schedule a service delivery."""
        # Implementation would depend on the specific service
        pass
        
    def get_stream_stats(self, stream_id: str) -> Dict[str, Any]:
        """Get statistics for a revenue stream."""
        try:
            res = self.execute_sql(f"""
                SELECT 
                    COUNT(*) as total_sales,
                    SUM(amount_cents) as total_revenue_cents,
                    MIN(created_at) as first_sale_at,
                    MAX(created_at) as last_sale_at
                FROM revenue_payments
                WHERE stream_id = '{stream_id}'
            """)
            stats = res.get("rows", [{}])[0]
            return {"success": True, "stats": stats}
        except Exception as e:
            return {"success": False, "error": str(e)}

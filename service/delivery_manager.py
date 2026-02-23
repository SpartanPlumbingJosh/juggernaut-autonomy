import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

from core.database import query_db
from core.logging import log_action

class ServiceDeliveryManager:
    """Manage automated service delivery after payment."""

    def process_new_orders(self) -> Dict:
        """Process all completed payments waiting for service delivery."""
        try:
            # Get orders with payment but no delivery
            sql = """
            SELECT p.id, p.payment_intent_id, p.amount, p.currency,
                   p.metadata->>'service_id' as service_id,
                   p.metadata->>'customer_id' as customer_id
            FROM payment_events p
            LEFT JOIN service_deliveries d ON p.payment_intent_id = d.payment_intent_id
            WHERE p.status = 'succeeded' AND d.id IS NULL
            LIMIT 100
            """
            result = query_db(sql)
            orders = result.get('rows', [])

            processed = 0
            for order in orders:
                self._deliver_service(order)
                processed += 1

            log_action("delivery.processed", f"Processed {processed} new orders")
            return {"success": True, "processed": processed}

        except Exception as e:
            log_action("delivery.failed", f"Failed to process orders: {str(e)}", level="error")
            return {"success": False, "error": str(e)}

    def _deliver_service(self, order: Dict) -> None:
        """Deliver the actual service for a paid order."""
        service_id = order.get('service_id')
        customer_id = order.get('customer_id')
        
        # Implementation varies by service type - this is a generic version
        token = self._generate_service_token(customer_id, service_id)
        expiry = datetime.now() + timedelta(days=30)  # Standard 30-day access
        
        try:
            sql = f"""
            INSERT INTO service_deliveries (
                id, payment_intent_id, customer_id,
                service_id, access_token, expiry_date,
                status, created_at
            ) VALUES (
                gen_random_uuid(),
                '{order['payment_intent_id']}',
                '{customer_id}',
                '{service_id}',
                '{token}',
                '{expiry.isoformat()}',
                'active',
                NOW()
            )
            """
            query_db(sql)
            
            # TODO: Send delivery email/notification
            log_action("delivery.completed", 
                      f"Delivered service {service_id} for payment {order['payment_intent_id']}")

        except Exception as e:
            log_action("delivery.failed", 
                      f"Failed to deliver service {service_id}: {str(e)}", 
                      level="error")
            raise

    def _generate_service_token(self, customer_id: str, service_id: str) -> str:
        """Generate a unique access token for the service."""
        # In production use proper crypto!
        import hashlib
        import secrets
        salt = secrets.token_hex(8)
        return hashlib.sha256(f"{customer_id}{service_id}{salt}".encode()).hexdigest()

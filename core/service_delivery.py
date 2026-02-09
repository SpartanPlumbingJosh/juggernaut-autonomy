from typing import Dict, List
import json
from datetime import datetime, timedelta

class ServiceDelivery:
    """Automated service delivery and provisioning system."""
    
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
    
    async def process_pending_services(self) -> Dict:
        """Process all pending service activations."""
        try:
            res = await self.execute_sql(
                """
                SELECT id, customer_id 
                FROM customer_services
                WHERE status = 'pending'
                LIMIT 50
                """
            )
            services = res.get('rows', [])
            
            activated = 0
            for service in services:
                service_id = service['id']
                customer_id = service['customer_id']
                
                # Activate service
                await self.execute_sql(
                    f"""
                    UPDATE customer_services
                    SET status = 'active',
                        activated_at = NOW(),
                        updated_at = NOW()
                    WHERE id = '{service_id}'
                    """
                )
                
                # Record revenue event
                await self._record_activation_event(customer_id, service_id)
                
                activated += 1
                
            return {
                "success": True,
                "activated": activated,
                "total": len(services)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _record_activation_event(self, customer_id: str, service_id: str) -> None:
        """Record revenue event for service activation."""
        try:
            await self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, customer_id, service_id,
                    event_type, amount_cents, currency,
                    recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{service_id}',
                    'revenue',
                    5000,  -- $50.00 in cents
                    'usd',
                    NOW(),
                    NOW()
                )
                """
            )
        except Exception:
            pass
    
    async def process_service_renewals(self) -> Dict:
        """Process service renewals for active subscriptions."""
        try:
            res = await self.execute_sql(
                """
                SELECT s.id, s.customer_id
                FROM customer_services s
                JOIN subscriptions sub ON s.customer_id = sub.customer_id
                WHERE s.status = 'active'
                  AND sub.status = 'active'
                  AND s.activated_at <= NOW() - INTERVAL '1 month'
                LIMIT 50
                """
            )
            services = res.get('rows', [])
            
            renewed = 0
            for service in services:
                service_id = service['id']
                customer_id = service['customer_id']
                
                # Record renewal revenue
                await self._record_activation_event(customer_id, service_id)
                
                # Update renewal timestamp
                await self.execute_sql(
                    f"""
                    UPDATE customer_services
                    SET last_renewed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = '{service_id}'
                    """
                )
                
                renewed += 1
                
            return {
                "success": True,
                "renewed": renewed,
                "total": len(services)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class ServiceDelivery:
    def __init__(self):
        self.default_service_duration = int(os.getenv('DEFAULT_SERVICE_DURATION', 30))  # in days

    async def create_service_order(self, user_id: str, service_type: str, 
                                 metadata: Optional[Dict] = None) -> Dict:
        """Create a new service order"""
        try:
            # Calculate service dates
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=self.default_service_duration)
            
            # Create service order
            await query_db(f"""
                INSERT INTO service_orders (
                    id, user_id, service_type, status,
                    start_date, end_date, metadata,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{user_id}',
                    '{service_type}',
                    'active',
                    '{start_date.isoformat()}',
                    '{end_date.isoformat()}',
                    '{json.dumps(metadata or {})}',
                    NOW(),
                    NOW()
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def check_service_status(self, user_id: str) -> Dict:
        """Check active services for a user"""
        try:
            services = await query_db(f"""
                SELECT id, service_type, status, 
                       start_date, end_date 
                FROM service_orders
                WHERE user_id = '{user_id}'
                  AND status = 'active'
            """)
            return {
                "success": True,
                "services": services.get('rows', [])
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def renew_service(self, service_id: str) -> Dict:
        """Renew an existing service"""
        try:
            # Get current service
            service = await query_db(f"""
                SELECT end_date FROM service_orders
                WHERE id = '{service_id}'
            """)
            if not service.get('rows'):
                return {"success": False, "error": "Service not found"}
            
            # Calculate new end date
            current_end = datetime.fromisoformat(service['rows'][0]['end_date'])
            new_end = current_end + timedelta(days=self.default_service_duration)
            
            # Update service
            await query_db(f"""
                UPDATE service_orders
                SET end_date = '{new_end.isoformat()}',
                    updated_at = NOW()
                WHERE id = '{service_id}'
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

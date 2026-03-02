from typing import Dict, Optional
from datetime import datetime
from core.database import query_db

class ServiceDelivery:
    def __init__(self):
        self.services = {}

    async def onboard_customer(self, customer_data: Dict) -> Dict:
        """Onboard new customer and provision services."""
        try:
            # Create customer record
            sql = f"""
            INSERT INTO customers (
                id, email, name, status,
                created_at, updated_at, metadata
            ) VALUES (
                gen_random_uuid(),
                '{customer_data.get("email")}',
                '{customer_data.get("name", "")}',
                'active',
                NOW(),
                NOW(),
                '{json.dumps(customer_data.get("metadata", {}))}'
            )
            """
            await query_db(sql)
            
            # Provision services
            services = customer_data.get("services", [])
            for service in services:
                await self.provision_service(service, customer_data)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def provision_service(self, service_name: str, customer_data: Dict) -> Dict:
        """Provision a specific service for customer."""
        try:
            # Check if service exists
            if service_name not in self.services:
                return {"success": False, "error": "Service not found"}
            
            # Call service provisioning logic
            result = await self.services[service_name].provision(customer_data)
            
            # Log service provisioning
            await query_db(f"""
                INSERT INTO service_events (
                    id, customer_id, service_name,
                    status, created_at, metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_data.get("id")}',
                    '{service_name}',
                    'provisioned',
                    NOW(),
                    '{json.dumps(result.get("metadata", {}))}'
                )
            """)
            
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def register_service(self, service_name: str, service_handler) -> Dict:
        """Register new service type."""
        self.services[service_name] = service_handler
        return {"success": True}

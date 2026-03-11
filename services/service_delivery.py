"""
Service Delivery - Handles provisioning and management of services.
"""

from typing import Dict, Any
from core.database import query_db

class ServiceDelivery:
    async def provision_service(self, customer_id: str, plan: str) -> Dict[str, Any]:
        """Provision services based on customer's plan."""
        try:
            # Get plan details
            plan_details = await query_db(f"""
                SELECT * FROM plans
                WHERE name = '{plan}'
                LIMIT 1
            """)
            
            if not plan_details.get('rows'):
                return {"success": False, "error": "Plan not found"}
            
            # Provision resources
            await query_db(f"""
                INSERT INTO customer_resources (
                    id, customer_id, plan, 
                    resource_type, quantity, provisioned_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan}',
                    'compute',
                    {plan_details['rows'][0]['compute_units']},
                    NOW()
                ),
                (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan}',
                    'storage',
                    {plan_details['rows'][0]['storage_gb']},
                    NOW()
                )
            """)
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def monitor_services(self) -> Dict[str, Any]:
        """Monitor and maintain active services."""
        try:
            # Check resource usage
            usage = await query_db("""
                SELECT customer_id, resource_type, 
                       SUM(quantity) as allocated,
                       SUM(usage) as used
                FROM customer_resources
                GROUP BY customer_id, resource_type
            """)
            
            # Check for overages
            overages = []
            for row in usage.get('rows', []):
                if row['used'] > row['allocated']:
                    overages.append({
                        'customer_id': row['customer_id'],
                        'resource_type': row['resource_type'],
                        'allocated': row['allocated'],
                        'used': row['used']
                    })
            
            return {
                "success": True,
                "usage": usage.get('rows', []),
                "overages": overages
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

from datetime import datetime
from typing import Dict, Optional
from core.database import query_db, execute_db

class ServiceProvisioner:
    async def provision_service(self, customer_id: str, plan_id: str) -> Dict[str, Any]:
        """Provision service resources for a new customer."""
        try:
            # Get plan details
            plan = await query_db(
                f"SELECT * FROM plans WHERE id = '{plan_id}'"
            )
            if not plan.get("rows"):
                return {"success": False, "error": "Plan not found"}
                
            plan_details = plan["rows"][0]
            
            # Create service record
            await execute_db(
                f"""
                INSERT INTO services (customer_id, plan_id, status, created_at)
                VALUES ('{customer_id}', '{plan_id}', 'active', NOW())
                """
            )
            
            # Provision resources based on plan
            resources = await self._allocate_resources(plan_details)
            
            return {
                "success": True,
                "resources": resources,
                "plan": plan_details
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _allocate_resources(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Allocate resources based on plan."""
        # Implement resource allocation logic here
        return {
            "cpu": plan.get("cpu_cores"),
            "memory": plan.get("memory_gb"),
            "storage": plan.get("storage_gb")
        }
        
    async def deprovision_service(self, customer_id: str) -> Dict[str, Any]:
        """Deprovision service resources."""
        try:
            await execute_db(
                f"""
                UPDATE services
                SET status = 'deprovisioned', deprovisioned_at = NOW()
                WHERE customer_id = '{customer_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

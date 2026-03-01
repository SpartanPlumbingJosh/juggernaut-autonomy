from typing import Any, Dict, List, Optional

class OnboardingManager:
    """Manage customer onboarding workflows."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    def start_onboarding(self, customer_id: str, product_id: str) -> Dict[str, Any]:
        """Start a new onboarding process."""
        try:
            onboarding_id = str(uuid.uuid4())
            self.execute_sql(f"""
                INSERT INTO onboarding (
                    id, customer_id, product_id, status, created_at
                ) VALUES (
                    '{onboarding_id}',
                    '{customer_id}',
                    '{product_id}',
                    'started',
                    NOW()
                )
            """)
            return {"success": True, "onboarding_id": onboarding_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def complete_step(self, onboarding_id: str, step_name: str) -> Dict[str, Any]:
        """Mark an onboarding step as completed."""
        try:
            self.execute_sql(f"""
                UPDATE onboarding
                SET steps_completed = array_append(steps_completed, '{step_name}'),
                    updated_at = NOW()
                WHERE id = '{onboarding_id}'
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_onboarding_status(self, onboarding_id: str) -> Dict[str, Any]:
        """Get current onboarding status."""
        try:
            result = self.execute_sql(f"""
                SELECT * FROM onboarding
                WHERE id = '{onboarding_id}'
            """)
            return result.get("rows", [{}])[0]
        except Exception as e:
            return {}

from typing import Dict, Optional
from datetime import datetime
import json

class CustomerOnboarding:
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action

    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new customer record."""
        try:
            customer_id = self._generate_customer_id()
            metadata_json = json.dumps(metadata or {})
            
            self.execute_sql(f"""
                INSERT INTO customers (
                    id, email, name, status, 
                    created_at, updated_at, metadata
                ) VALUES (
                    '{customer_id}',
                    '{email}',
                    '{name}',
                    'pending',
                    NOW(),
                    NOW(),
                    '{metadata_json}'::jsonb
                )
            """)
            
            self.log_action(
                "customer.created",
                f"New customer created: {email}",
                level="info",
                output_data={"customer_id": customer_id}
            )
            
            return {"success": True, "customer_id": customer_id}
        except Exception as e:
            self.log_action(
                "customer.creation_failed",
                f"Failed to create customer: {str(e)}",
                level="error",
                error_data={"email": email, "error": str(e)}
            )
            return {"success": False, "error": str(e)}

    def complete_onboarding(self, customer_id: str) -> Dict:
        """Mark customer onboarding as complete."""
        try:
            self.execute_sql(f"""
                UPDATE customers
                SET status = 'active',
                    onboarded_at = NOW(),
                    updated_at = NOW()
                WHERE id = '{customer_id}'
            """)
            
            self.log_action(
                "customer.onboarded",
                f"Customer onboarding completed: {customer_id}",
                level="info",
                output_data={"customer_id": customer_id}
            )
            
            return {"success": True}
        except Exception as e:
            self.log_action(
                "customer.onboarding_failed",
                f"Failed to complete onboarding: {str(e)}",
                level="error",
                error_data={"customer_id": customer_id, "error": str(e)}
            )
            return {"success": False, "error": str(e)}

    def _generate_customer_id(self) -> str:
        """Generate a unique customer ID."""
        # Implementation depends on your ID generation strategy
        return f"cust_{datetime.now().strftime('%Y%m%d%H%M%S')}"

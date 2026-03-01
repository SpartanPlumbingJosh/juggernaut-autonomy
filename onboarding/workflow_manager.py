from typing import Dict, Optional
from datetime import datetime

from core.database import query_db
from core.logging import log_action

class OnboardingWorkflow:
    """Manage customer onboarding steps and progression."""

    def start_onboarding(self, email: str) -> Dict:
        """Start new customer onboarding."""
        try:
            # Check if already exists
            check_sql = f"""
            SELECT id FROM customers WHERE email = '{email.replace("'", "''")}'
            """
            existing = query_db(check_sql)
            
            if existing.get('rows'):
                return {"success": False, "error": "Customer already exists"}
            
            # Create new customer
            sql = f"""
            INSERT INTO customers (
                id, email, status, 
                onboarding_step, created_at
            ) VALUES (
                gen_random_uuid(),
                '{email.replace("'", "''")}',
                'pending',
                'initial',
                NOW()
            )
            RETURNING id
            """
            result = query_db(sql)
            customer_id = result['rows'][0]['id']
            
            log_action("onboarding.started", f"Started onboarding for {email}")
            
            # Queue welcome email
            self._send_welcome_email(email)
            
            return {
                "success": True,
                "customer_id": customer_id,
                "next_step": "profile_completion"
            }
        except Exception as e:
            log_action("onboarding.failed", f"Failed to start onboarding: {str(e)}", level="error")
            return {"success": False, "error": str(e)}

    def complete_step(self, customer_id: str, step: str) -> Dict:
        """Mark an onboarding step as completed."""
        try:
            sql = f"""
            UPDATE customers
            SET onboarding_step = '{step.replace("'", "''")}',
                updated_at = NOW()
            WHERE id = '{customer_id.replace("'", "''")}'
            """
            query_db(sql)
            
            log_action("onboarding.step_completed", 
                      f"Completed {step} for customer {customer_id}")

            # Check if onboarding complete
            if step == "payment_method_added":
                self._finalize_onboarding(customer_id)
                
            return {"success": True}
        except Exception as e:
            log_action("onboarding.step_failed", 
                      f"Failed to complete step {step}: {str(e)}", 
                      level="error")
            return {"success": False, "error": str(e)}

    def _send_welcome_email(self, email: str) -> None:
        """Send welcome email to new customer."""
        # TODO: Actual email integration
        log_action("email.sent", f"Sent welcome email to {email}")

    def _finalize_onboarding(self, customer_id: str) -> None:
        """Mark onboarding as complete and grant initial access."""
        sql = f"""
        UPDATE customers
        SET status = 'active',
            onboarding_completed_at = NOW()
        WHERE id = '{customer_id.replace("'", "''")}'
        """
        query_db(sql)
        log_action("onboarding.completed", f"Completed onboarding for {customer_id}")

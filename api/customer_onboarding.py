import json
from typing import Dict, Optional
from datetime import datetime
from core.database import query_db

class CustomerOnboarding:
    def __init__(self):
        self.welcome_email_template = "..."  # Should be from config

    async def create_customer(self, customer_data: Dict) -> Dict:
        """Create a new customer record"""
        try:
            result = await query_db(f"""
                INSERT INTO customers (
                    id, email, name, created_at, metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_data.get("email")}',
                    '{customer_data.get("name")}',
                    NOW(),
                    '{json.dumps(customer_data)}'::jsonb
                )
                RETURNING id
            """)
            customer_id = result.get("rows", [{}])[0].get("id")
            return {
                "success": True,
                "customer_id": customer_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def send_welcome_email(self, customer_id: str) -> Dict:
        """Send welcome email to new customer"""
        try:
            # TODO: Implement actual email sending logic
            # This could use SendGrid, Mailgun, etc.
            
            await query_db(f"""
                INSERT INTO customer_emails (
                    id, customer_id, email_type, sent_at, status
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    'welcome',
                    NOW(),
                    'sent'
                )
            """)
            
            return {
                "success": True,
                "message": "Welcome email sent"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def complete_onboarding(self, customer_id: str) -> Dict:
        """Complete the onboarding process"""
        try:
            await query_db(f"""
                UPDATE customers
                SET onboarding_complete = TRUE,
                    updated_at = NOW()
                WHERE id = '{customer_id}'
            """)
            return {
                "success": True,
                "message": "Onboarding completed"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

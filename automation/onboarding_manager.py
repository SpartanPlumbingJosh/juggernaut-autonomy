from typing import Dict
from core.database import query_db, execute_sql
from datetime import datetime

class OnboardingManager:
    async def create_user(self, email: str, password: str, metadata: Dict) -> Dict:
        """Create new user account"""
        try:
            # Check if user exists
            existing = await query_db(
                f"SELECT id FROM users WHERE email = '{email}'"
            )
            if existing.get('rows'):
                return {"success": False, "error": "User already exists"}
                
            # Create user
            await execute_sql(
                f"""
                INSERT INTO users (
                    id, email, password_hash, 
                    status, created_at, updated_at, 
                    metadata
                ) VALUES (
                    gen_random_uuid(),
                    '{email}',
                    crypt('{password}', gen_salt('bf')),
                    'active',
                    NOW(),
                    NOW(),
                    '{json.dumps(metadata)}'
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def complete_onboarding(self, user_id: str) -> Dict:
        """Complete user onboarding process"""
        try:
            # Update user status
            await execute_sql(
                f"""
                UPDATE users 
                SET onboarding_complete = TRUE,
                    updated_at = NOW()
                WHERE id = '{user_id}'
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

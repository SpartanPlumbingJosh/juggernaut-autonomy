from typing import Dict, Optional
from core.database import execute_sql
from datetime import datetime

class ErrorHandler:
    async def log_error(self, error_type: str, message: str, context: Optional[Dict] = None) -> None:
        """Log system errors"""
        await execute_sql(
            f"""
            INSERT INTO system_errors (
                id, error_type, message, 
                context, created_at
            ) VALUES (
                gen_random_uuid(),
                '{error_type}',
                '{message}',
                '{json.dumps(context or {})}',
                NOW()
            )
            """
        )
        
    async def handle_failed_payment(self, payment_id: str, error: str) -> None:
        """Handle payment failures"""
        await execute_sql(
            f"""
            UPDATE payments 
            SET status = 'failed',
                error_message = '{error}',
                updated_at = NOW()
            WHERE id = '{payment_id}'
            """
        )
        
    async def handle_failed_fulfillment(self, order_id: str, error: str) -> None:
        """Handle fulfillment failures"""
        await execute_sql(
            f"""
            UPDATE orders 
            SET status = 'fulfillment_failed',
                error_message = '{error}',
                updated_at = NOW()
            WHERE id = '{order_id}'
            """
        )

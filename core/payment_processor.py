"""Payment processing strategy implementation."""
import json
from datetime import datetime
from typing import Any, Dict, Optional

class PaymentProcessor:
    """Handles all payment processing operations."""
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def process_payment(self, amount: float, description: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process a payment transaction."""
        try:
            # Record the revenue event
            result = self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, experiment_id, event_type,
                    amount_cents, currency, source,
                    metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(), 
                    {f"'{metadata.get('experiment_id')}'" if metadata.get('experiment_id') else 'NULL'},
                    'revenue',
                    {int(amount * 100)},  -- Convert to cents
                    'USD',
                    'payment_processor',
                    '{json.dumps(metadata)}',
                    NOW()
                )
                RETURNING id
                """
            )
            
            transaction_id = result.get("rows", [{}])[0].get("id")
            
            self.log_action(
                "payment.processed",
                f"Processed payment of ${amount:.2f}",
                level="info",
                output_data={
                    "amount": amount,
                    "transaction_id": transaction_id
                }
            )
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "amount": amount
            }
            
        except Exception as e:
            self.log_action(
                "payment.failed",
                f"Payment processing failed: {str(e)}",
                level="error",
                error_data={
                    "error": str(e),
                    "amount": amount
                }
            )
            return {
                "success": False,
                "error": str(e)
            }

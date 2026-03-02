"""Digital product distribution implementation."""
import json
from datetime import datetime
from typing import Any, Dict, Optional

class DigitalProduct:
    """Handles digital product distribution and revenue recording."""
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def distribute_product(self, product_config: Dict[str, Any]) -> Dict[str, Any]:
        """Distribute digital product and record revenue."""
        try:
            amount = float(product_config.get("price", 0))
            
            # Record the product sale
            result = self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, experiment_id, event_type,
                    amount_cents, currency, source,
                    metadata, recorded_at
                ) VALUES (
                    gen_random_uuid(), 
                    {f"'{product_config.get('experiment_id')}'" if product_config.get('experiment_id') else 'NULL'},
                    'revenue',
                    {int(amount * 100)},  -- Convert to cents
                    'USD',
                    'digital_product',
                    '{json.dumps(product_config)}',
                    NOW()
                )
                RETURNING id
                """
            )
            
            transaction_id = result.get("rows", [{}])[0].get("id")
            
            self.log_action(
                "product.distributed",
                f"Distributed digital product with price ${amount:.2f}",
                level="info",
                output_data={
                    "amount": amount,
                    "transaction_id": transaction_id,
                    "product_type": product_config.get("product_type")
                }
            )
            
            # TODO: Actual product delivery implementation would go here
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "amount": amount
            }
            
        except Exception as e:
            self.log_action(
                "product.failed",
                f"Product distribution failed: {str(e)}",
                level="error",
                error_data={
                    "error": str(e),
                    "product_config": product_config
                }
            )
            return {
                "success": False,
                "error": str(e)
            }

"""
Revenue Validation Service - Core logic for validating and tracking revenue models.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

class RevenueValidator:
    """Validates revenue models and tracks performance metrics."""
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.min_validation_period = timedelta(days=7)  # Minimum validation period
    
    async def validate_model(self, model_id: str) -> Dict:
        """Validate a revenue model and return performance metrics."""
        try:
            # Get model details
            model = await self._get_model(model_id)
            if not model:
                return {"success": False, "error": "Model not found"}
            
            # Check if model has enough validation time
            created_at = model.get("created_at")
            if datetime.now() - created_at < self.min_validation_period:
                return {"success": False, "error": "Insufficient validation period"}
            
            # Calculate performance metrics
            metrics = await self._calculate_metrics(model_id)
            
            # Update model status
            await self._update_model_status(model_id, metrics)
            
            return {"success": True, "metrics": metrics}
            
        except Exception as e:
            self.log_action(
                "revenue.validation_failed",
                f"Failed to validate model {model_id}",
                level="error",
                error_data={"model_id": model_id, "error": str(e)}
            )
            return {"success": False, "error": str(e)}
    
    async def _get_model(self, model_id: str) -> Optional[Dict]:
        """Retrieve model details from database."""
        result = await self.execute_sql(
            f"SELECT * FROM revenue_models WHERE id = '{model_id}'"
        )
        return result.get("rows", [{}])[0] if result else None
    
    async def _calculate_metrics(self, model_id: str) -> Dict:
        """Calculate key performance metrics for the model."""
        # Get revenue events for this model
        result = await self.execute_sql(f"""
            SELECT 
                SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
                SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents,
                COUNT(*) FILTER (WHERE event_type = 'revenue') as transactions,
                MIN(recorded_at) as first_transaction,
                MAX(recorded_at) as last_transaction
            FROM revenue_events
            WHERE model_id = '{model_id}'
        """)
        
        metrics = result.get("rows", [{}])[0]
        metrics["roi"] = (
            (metrics["revenue_cents"] - metrics["cost_cents"]) / 
            metrics["cost_cents"] * 100
        ) if metrics["cost_cents"] > 0 else 0
        
        return metrics
    
    async def _update_model_status(self, model_id: str, metrics: Dict) -> None:
        """Update model status based on validation results."""
        status = "validated" if metrics["roi"] > 0 else "invalidated"
        
        await self.execute_sql(f"""
            UPDATE revenue_models
            SET 
                status = '{status}',
                validation_metrics = '{json.dumps(metrics)}',
                validated_at = NOW()
            WHERE id = '{model_id}'
        """)
        
        self.log_action(
            "revenue.model_validated",
            f"Model {model_id} validated with ROI {metrics['roi']}%",
            level="info",
            output_data={"model_id": model_id, "metrics": metrics}
        )

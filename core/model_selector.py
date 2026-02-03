"""
Model Selector

Intelligently selects the best model for each task based on routing policies.

Part of Milestone 6: OpenRouter Smart Routing
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from core.database import fetch_all, execute_sql

logger = logging.getLogger(__name__)


class ModelSelector:
    """Selects optimal models for tasks based on policies."""
    
    def get_task_policy(self, task: Dict[str, Any]) -> str:
        """
        Determine which routing policy to use for a task.
        
        Args:
            task: Task data
            
        Returns:
            Policy name
        """
        task_type = task.get('task_type', 'generic')
        
        # Map task types to policies
        policy_map = {
            'investigate_error': 'code',
            'fix_bug': 'code',
            'deploy_code': 'code',
            'analyze_logs': 'normal',
            'update_dependency': 'code',
            'create_pr': 'code',
            'simple_query': 'ops',
            'health_check': 'ops',
            'status_update': 'ops',
            'research': 'deep_research',
            'strategic_analysis': 'deep_research',
            'generic': 'normal'
        }
        
        return policy_map.get(task_type, 'normal')
    
    def get_policy_config(self, policy_name: str) -> Optional[Dict[str, Any]]:
        """
        Get routing policy configuration.
        
        Args:
            policy_name: Policy name
            
        Returns:
            Policy config or None
        """
        try:
            query = """
                SELECT policy_config
                FROM routing_policies
                WHERE name = %s AND is_active = TRUE
            """
            results = fetch_all(query, (policy_name,))
            
            if results:
                config = results[0]['policy_config']
                if isinstance(config, str):
                    import json
                    return json.loads(config)
                return config
            
            return None
        except Exception as e:
            logger.exception(f"Error getting policy config: {e}")
            return None
    
    def get_model_performance(self, model_name: str, provider: str) -> Dict[str, Any]:
        """
        Get recent performance metrics for a model.
        
        Args:
            model_name: Model name
            provider: Provider name
            
        Returns:
            Performance metrics
        """
        try:
            query = """
                SELECT 
                    total_requests,
                    successful_requests,
                    failed_requests,
                    avg_response_time_ms,
                    total_cost
                FROM model_performance
                WHERE 
                    model_name = %s
                    AND provider = %s
                    AND window_end > NOW() - INTERVAL '24 hours'
                ORDER BY window_end DESC
                LIMIT 1
            """
            results = fetch_all(query, (model_name, provider))
            
            if results:
                perf = results[0]
                total = int(perf.get('total_requests', 0))
                successful = int(perf.get('successful_requests', 0))
                
                return {
                    'success_rate': successful / total if total > 0 else 0.5,
                    'avg_response_time': int(perf.get('avg_response_time_ms', 0)),
                    'total_cost': float(perf.get('total_cost', 0))
                }
            
            return {
                'success_rate': 0.5,
                'avg_response_time': 0,
                'total_cost': 0
            }
        except Exception as e:
            logger.exception(f"Error getting model performance: {e}")
            return {'success_rate': 0.5, 'avg_response_time': 0, 'total_cost': 0}
    
    def check_budget_available(self, estimated_cost: float) -> bool:
        """
        Check if budget is available for estimated cost.
        
        Args:
            estimated_cost: Estimated cost in dollars
            
        Returns:
            True if budget available
        """
        try:
            query = """
                SELECT 
                    budget_amount,
                    spent_amount,
                    alert_threshold
                FROM cost_budgets
                WHERE 
                    is_active = TRUE
                    AND budget_period = 'daily'
                    AND period_start <= NOW()
                    AND period_end > NOW()
                ORDER BY created_at DESC
                LIMIT 1
            """
            results = fetch_all(query)
            
            if not results:
                return True  # No budget set, allow
            
            budget = results[0]
            budget_amount = float(budget.get('budget_amount', 0))
            spent_amount = float(budget.get('spent_amount', 0))
            
            remaining = budget_amount - spent_amount
            return remaining >= estimated_cost
        except Exception as e:
            logger.exception(f"Error checking budget: {e}")
            return True  # Allow on error
    
    def select_model(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Select the best model for a task.
        
        Args:
            task: Task data
            
        Returns:
            Selected model info or None
        """
        # Get policy for task
        policy_name = self.get_task_policy(task)
        policy_config = self.get_policy_config(policy_name)
        
        if not policy_config:
            logger.error(f"No policy config found for {policy_name}")
            return None
        
        models = policy_config.get('models', [])
        max_cost = float(policy_config.get('max_cost_per_task', 1.0))
        
        # Check budget
        if not self.check_budget_available(max_cost):
            logger.warning("Budget exceeded, cannot select model")
            return None
        
        # Sort models by priority
        sorted_models = sorted(models, key=lambda m: m.get('priority', 999))
        
        # Select first available model with good performance
        for model_config in sorted_models:
            model_name = model_config.get('model')
            provider = model_config.get('provider')
            
            # Get performance metrics
            perf = self.get_model_performance(model_name, provider)
            
            # Require at least 30% success rate
            if perf['success_rate'] >= 0.3:
                return {
                    'model': model_name,
                    'provider': provider,
                    'policy': policy_name,
                    'estimated_cost': max_cost,
                    'max_tokens': policy_config.get('max_tokens', 4000),
                    'temperature': policy_config.get('temperature', 0.7)
                }
        
        # If no model meets criteria, use first model anyway
        if sorted_models:
            model_config = sorted_models[0]
            return {
                'model': model_config.get('model'),
                'provider': model_config.get('provider'),
                'policy': policy_name,
                'estimated_cost': max_cost,
                'max_tokens': policy_config.get('max_tokens', 4000),
                'temperature': policy_config.get('temperature', 0.7)
            }
        
        return None
    
    def record_selection(
        self,
        task_id: str,
        selection: Dict[str, Any],
        actual_cost: Optional[float] = None,
        tokens_used: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        success: Optional[bool] = None,
        error_message: Optional[str] = None
    ):
        """
        Record a model selection for tracking.
        
        Args:
            task_id: Task ID
            selection: Selection info
            actual_cost: Actual cost (if known)
            tokens_used: Tokens used (if known)
            response_time_ms: Response time (if known)
            success: Whether successful (if known)
            error_message: Error message (if failed)
        """
        try:
            query = """
                INSERT INTO model_selections (
                    task_id,
                    policy_name,
                    selected_model,
                    selected_provider,
                    estimated_cost,
                    actual_cost,
                    tokens_used,
                    response_time_ms,
                    success,
                    error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            execute_sql(query, (
                task_id,
                selection.get('policy'),
                selection.get('model'),
                selection.get('provider'),
                selection.get('estimated_cost'),
                actual_cost,
                tokens_used,
                response_time_ms,
                success,
                error_message
            ))
            
            # Update budget if actual cost known
            if actual_cost is not None:
                self.update_budget_spent(actual_cost)
        except Exception as e:
            logger.exception(f"Error recording selection: {e}")
    
    def update_budget_spent(self, amount: float):
        """Update spent amount in budget."""
        try:
            query = """
                UPDATE cost_budgets
                SET 
                    spent_amount = spent_amount + %s,
                    updated_at = %s
                WHERE 
                    is_active = TRUE
                    AND budget_period = 'daily'
                    AND period_start <= NOW()
                    AND period_end > NOW()
            """
            execute_sql(query, (amount, datetime.now(timezone.utc).isoformat()))
        except Exception as e:
            logger.exception(f"Error updating budget: {e}")


# Singleton instance
_model_selector = None


def get_model_selector() -> ModelSelector:
    """Get or create model selector singleton."""
    global _model_selector
    if _model_selector is None:
        _model_selector = ModelSelector()
    return _model_selector


__all__ = ["ModelSelector", "get_model_selector"]

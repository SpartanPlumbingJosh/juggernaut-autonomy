from typing import Dict, Any, Callable
import math
from datetime import datetime, timedelta

class PriceOptimizationAgent:
    """Agent to optimize pricing based on demand elasticity and revenue targets."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.target_revenue = 16_000_000 * 100  # $16M in cents
        self.price_adjustment_rate = 0.05  # Max % change per adjustment
        
    async def analyze_price_sensitivity(self) -> Dict[str, float]:
        """Analyze price elasticity based on historical data."""
        try:
            res = await self.execute_sql("""
                SELECT price_point, SUM(quantity) as total_units, SUM(revenue_cents) as total_revenue
                FROM price_experiments
                WHERE recorded_at >= NOW() - INTERVAL '30 days'
                GROUP BY price_point
                ORDER BY price_point
            """)
            return {str(r['price_point']): r['total_revenue'] for r in res.get('rows', [])}
        except Exception as e:
            self.log_action("price_analysis_failed", str(e), level="error")
            return {}

    async def optimize_prices(self) -> Dict[str, Any]:
        """Adjust prices to maximize revenue growth toward target."""
        try:
            sensitivity = await self.analyze_price_sensitivity()
            if not sensitivity:
                return {"success": False, "message": "No price sensitivity data"}
                
            # Find price point with highest revenue
            best_price = max(sensitivity.items(), key=lambda x: x[1])[0]
            current_price = await self.get_current_price()
            
            # Calculate adjustment needed
            price_diff = float(best_price) - float(current_price)
            adjustment = price_diff * self.price_adjustment_rate
            
            # Apply new price
            await self.execute_sql(f"""
                UPDATE product_prices
                SET price_cents = price_cents * {1 + adjustment}
                WHERE product_id IN (
                    SELECT id FROM products WHERE status = 'active'
                )
            """)
            
            return {"success": True, "new_price": float(current_price) * (1 + adjustment)}
        except Exception as e:
            self.log_action("price_optimization_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

class ResourceAllocationAgent:
    """Agent to optimize resource allocation across experiments."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.min_budget = 1000  # $10 minimum per experiment
        self.max_budget = 100000  # $1000 maximum per experiment
        
    async def allocate_budgets(self) -> Dict[str, Any]:
        """Reallocate budgets based on ROI projections."""
        try:
            # Get ROI projections for active experiments
            res = await self.execute_sql("""
                SELECT id, projected_roi, budget_spent, budget_limit
                FROM experiments
                WHERE status = 'running'
                ORDER BY projected_roi DESC
            """)
            experiments = res.get('rows', [])
            
            # Calculate total available budget
            total_budget = sum(min(e['budget_limit'], self.max_budget) - e['budget_spent'] 
                             for e in experiments)
            
            # Allocate based on ROI
            allocations = {}
            for exp in experiments:
                roi_weight = math.sqrt(exp['projected_roi'] / 100)  # Square root to reduce extreme allocations
                allocation = total_budget * roi_weight
                allocations[exp['id']] = min(allocation, self.max_budget)
            
            # Apply new budgets
            for exp_id, budget in allocations.items():
                await self.execute_sql(f"""
                    UPDATE experiments
                    SET budget_limit = {budget}
                    WHERE id = '{exp_id}'
                """)
            
            return {"success": True, "allocations": allocations}
        except Exception as e:
            self.log_action("budget_allocation_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

class DemandScalingAgent:
    """Agent to scale resources based on demand forecasts."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.scale_up_threshold = 0.8  # 80% capacity utilization
        self.scale_down_threshold = 0.3  # 30% capacity utilization
        
    async def scale_resources(self) -> Dict[str, Any]:
        """Adjust resource allocation based on demand."""
        try:
            # Get current utilization
            res = await self.execute_sql("""
                SELECT resource_type, 
                       SUM(allocated) as total_allocated,
                       SUM(capacity) as total_capacity
                FROM resource_allocations
                GROUP BY resource_type
            """)
            resources = res.get('rows', [])
            
            actions = {}
            for resource in resources:
                utilization = resource['total_allocated'] / resource['total_capacity']
                if utilization > self.scale_up_threshold:
                    # Scale up by 20%
                    new_capacity = resource['total_capacity'] * 1.2
                    await self.execute_sql(f"""
                        UPDATE resource_allocations
                        SET capacity = {new_capacity}
                        WHERE resource_type = '{resource['resource_type']}'
                    """)
                    actions[resource['resource_type']] = f"Scaled up to {new_capacity}"
                elif utilization < self.scale_down_threshold:
                    # Scale down by 20%
                    new_capacity = resource['total_capacity'] * 0.8
                    await self.execute_sql(f"""
                        UPDATE resource_allocations
                        SET capacity = {new_capacity}
                        WHERE resource_type = '{resource['resource_type']}'
                    """)
                    actions[resource['resource_type']] = f"Scaled down to {new_capacity}"
            
            return {"success": True, "actions": actions}
        except Exception as e:
            self.log_action("scaling_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

class RevenueGrowthMonitor:
    """Monitor revenue growth and adjust strategies to reach target."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.target_revenue = 16_000_000 * 100  # $16M in cents
        self.growth_rate_window = 30  # Days to analyze growth rate
        
    async def calculate_growth_rate(self) -> float:
        """Calculate current revenue growth rate."""
        try:
            res = await self.execute_sql(f"""
                SELECT 
                    SUM(amount_cents) FILTER (WHERE event_type = 'revenue') as total_revenue,
                    DATE(recorded_at) as date
                FROM revenue_events
                WHERE recorded_at >= NOW() - INTERVAL '{self.growth_rate_window} days'
                GROUP BY DATE(recorded_at)
                ORDER BY date DESC
            """)
            daily_revenues = [r['total_revenue'] for r in res.get('rows', [])]
            if len(daily_revenues) < 2:
                return 0.0
            return (daily_revenues[0] - daily_revenues[-1]) / daily_revenues[-1]
        except Exception as e:
            self.log_action("growth_rate_calculation_failed", str(e), level="error")
            return 0.0
            
    async def adjust_strategies(self) -> Dict[str, Any]:
        """Adjust optimization strategies based on growth rate."""
        try:
            growth_rate = await self.calculate_growth_rate()
            required_growth = (self.target_revenue - await self.get_current_revenue()) / self.target_revenue
            
            if growth_rate < required_growth:
                # Increase aggressiveness of optimizations
                return {"success": True, "action": "increase_optimization_aggressiveness"}
            else:
                # Maintain current strategy
                return {"success": True, "action": "maintain_strategy"}
        except Exception as e:
            self.log_action("strategy_adjustment_failed", str(e), level="error")
            return {"success": False, "error": str(e)}

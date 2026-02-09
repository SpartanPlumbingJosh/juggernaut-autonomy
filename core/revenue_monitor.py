from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
import math
import numpy as np
from scipy.stats import linregress

from core.database import query_db

class RevenueMonitor:
    """Automated monitoring of revenue performance against targets."""
    
    TARGET_2030 = 10_000_000  # $10M target by 2030
    ALERT_THRESHOLD = 0.15  # 15% deviation triggers alert
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
    
    async def calculate_current_arr(self) -> float:
        """Calculate Annual Recurring Revenue from last 90 days data."""
        sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END)/100 as revenue,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END)/100 as cost
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '90 days'
        """
        result = await query_db(sql)
        row = result.get("rows", [{}])[0]
        
        # Scale 90 day revenue to annual
        revenue = float(row.get("revenue", 0))
        cost = float(row.get("cost", 0))
        current_arr = (revenue / 90) * 365
        burn_rate = (cost / 90) * 365
        
        return current_arr, burn_rate
    
    def calculate_runway(self, current_cash: float, burn_rate: float) -> float:
        """Calculate runway in months given current cash and burn rate."""
        if burn_rate <= 0:
            return float('inf')
        return (current_cash / burn_rate) * 12
    
    def calculate_growth_path(self, current_arr: float) -> Tuple[List[Dict], float]:
        """Calculate required growth trajectory to hit $10M target."""
        now = datetime.now(timezone.utc)
        target_date = datetime(2030, 1, 1, tzinfo=timezone.utc)
        months_remaining = (target_date.year - now.year) * 12 + (target_date.month - now.month)
        
        if months_remaining <= 0:
            return [], 0.0
        
        # Calculate required monthly growth rate using compound growth formula
        required_rate = (self.TARGET_2030 / current_arr) ** (1/months_remaining) - 1
        
        # Generate monthly projections
        projections = []
        current = current_arr
        for month in range(months_remaining + 1):
            projections.append({
                "month": (now + timedelta(days=30*month)).strftime("%Y-%m"),
                "projected_arr": current,
                "target_rate": required_rate * 100  # as percentage
            })
            current *= (1 + required_rate)
        
        return projections, required_rate * 100
    
    async def analyze_trajectory(self, current_cash: float) -> Dict:
        """Run complete revenue analysis and return report."""
        current_arr, burn_rate = await self.calculate_current_arr()
        runway_months = self.calculate_runway(current_cash, burn_rate)
        projections, required_rate = self.calculate_growth_path(current_arr)
        
        # Get actual growth trend from last 6 months
        sql = """
        SELECT 
            DATE_TRUNC('month', recorded_at) as month,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END)/100 as revenue
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '6 months'
        GROUP BY month
        ORDER BY month ASC
        """
        result = await query_db(sql)
        historical = result.get("rows", [])
        
        # Calculate actual growth rate
        actual_rate = 0.0
        if len(historical) > 1:
            x = np.arange(len(historical))
            y = np.array([h['revenue'] for h in historical])
            slope, _, _, _, _ = linregress(x, y)
            if y[0] > 0:
                actual_rate = (slope * 12 / y[0]) * 100  # annualized percentage
        
        # Check for alerts
        deviation = abs(actual_rate - required_rate) / required_rate
        alert = deviation > self.ALERT_THRESHOLD
        
        report = {
            "current_arr": current_arr,
            "burn_rate": burn_rate,
            "runway_months": runway_months,
            "required_growth_rate": required_rate,
            "actual_growth_rate": actual_rate,
            "deviation_percent": deviation * 100,
            "alert_status": alert,
            "projections": projections,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "cash_position": current_cash
        }
        
        if alert:
            await self.log_action(
                "revenue.alert",
                f"Revenue growth deviation detected: {actual_rate:.1f}% vs required {required_rate:.1f}%",
                level="warning",
                output_data=report
            )
        
        return report


async def daily_monitor_check(execute_sql: callable, log_action: callable, current_cash: float) -> Dict:
    """Run daily monitoring check and return results."""
    monitor = RevenueMonitor(execute_sql, log_action)
    report = await monitor.analyze_trajectory(current_cash)
    
    # Log the daily report
    await log_action(
        "revenue.monitor",
        "Daily revenue monitoring completed",
        level="info",
        output_data=report
    )
    
    return report

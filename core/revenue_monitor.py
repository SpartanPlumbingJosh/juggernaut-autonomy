from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import math

TARGET_REVENUE_CENTS = 1400000000  # $14M target
TARGET_YEAR = 2032  # Target year to achieve goal

class RevenueMonitor:
    """Track revenue progress and generate alerts."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def get_current_progress(self) -> Dict[str, Any]:
        """Get current revenue progress against target."""
        now = datetime.now()
        sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost
        FROM revenue_events
        """
        result = self.execute_sql(sql)
        total_revenue = result.get("rows", [{}])[0].get("total_revenue", 0)
        total_cost = result.get("rows", [{}])[0].get("total_cost", 0)
        
        # Calculate progress metrics
        years_remaining = TARGET_YEAR - now.year
        months_remaining = years_remaining * 12 + (12 - now.month)
        days_remaining = (datetime(TARGET_YEAR, 12, 31) - now).days
        
        required_daily = (TARGET_REVENUE_CENTS - total_revenue) / days_remaining if days_remaining > 0 else 0
        required_monthly = (TARGET_REVENUE_CENTS - total_revenue) / months_remaining if months_remaining > 0 else 0
        
        return {
            "current_revenue": total_revenue,
            "current_cost": total_cost,
            "target_revenue": TARGET_REVENUE_CENTS,
            "years_remaining": years_remaining,
            "months_remaining": months_remaining,
            "days_remaining": days_remaining,
            "required_daily": required_daily,
            "required_monthly": required_monthly,
            "progress_percent": (total_revenue / TARGET_REVENUE_CENTS) * 100,
            "runway_months": total_revenue / (total_cost / months_remaining) if total_cost > 0 else 0
        }
        
    def check_velocity(self) -> Optional[Dict[str, Any]]:
        """Check if current velocity meets required pace."""
        progress = self.get_current_progress()
        
        # Get last 30 days revenue
        sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as recent_revenue
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '30 days'
        """
        result = self.execute_sql(sql)
        recent_revenue = result.get("rows", [{}])[0].get("recent_revenue", 0)
        
        # Calculate velocity metrics
        daily_velocity = recent_revenue / 30
        monthly_velocity = recent_revenue
        velocity_shortfall = max(0, progress["required_daily"] - daily_velocity)
        
        if velocity_shortfall > 0:
            return {
                "alert_type": "velocity_shortfall",
                "daily_velocity": daily_velocity,
                "required_daily": progress["required_daily"],
                "shortfall": velocity_shortfall,
                "message": f"Revenue velocity shortfall: Current ${daily_velocity/100:.2f}/day vs required ${progress['required_daily']/100:.2f}/day"
            }
        return None
        
    def check_milestones(self) -> List[Dict[str, Any]]:
        """Check for milestone achievements."""
        progress = self.get_current_progress()
        milestones = []
        
        # Major percentage milestones
        for pct in [10, 25, 50, 75, 90, 100]:
            if progress["progress_percent"] >= pct and progress["progress_percent"] - pct < 1:
                milestones.append({
                    "alert_type": "milestone_achieved",
                    "milestone": f"{pct}%",
                    "message": f"Achieved {pct}% of revenue target!"
                })
                
        # Major dollar milestones
        for amount in [100000000, 250000000, 500000000, 750000000, 1000000000]:
            if progress["current_revenue"] >= amount and progress["current_revenue"] - amount < 100000:
                milestones.append({
                    "alert_type": "milestone_achieved",
                    "milestone": f"${amount/100:,.0f}",
                    "message": f"Reached ${amount/100:,.0f} in total revenue!"
                })
                
        return milestones
        
    def check_runway(self) -> Optional[Dict[str, Any]]:
        """Check runway based on current burn rate."""
        progress = self.get_current_progress()
        
        # Get last 90 days cost
        sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as recent_cost
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '90 days'
        """
        result = self.execute_sql(sql)
        recent_cost = result.get("rows", [{}])[0].get("recent_cost", 0)
        
        avg_monthly_cost = recent_cost / 3
        runway_months = progress["current_revenue"] / avg_monthly_cost if avg_monthly_cost > 0 else 0
        
        if runway_months < 6:
            return {
                "alert_type": "runway_warning",
                "runway_months": runway_months,
                "message": f"Runway warning: Only {runway_months:.1f} months remaining at current burn rate"
            }
        return None
        
    def generate_alerts(self) -> List[Dict[str, Any]]:
        """Generate all revenue monitoring alerts."""
        alerts = []
        
        # Velocity check
        velocity_alert = self.check_velocity()
        if velocity_alert:
            alerts.append(velocity_alert)
            
        # Milestone checks
        alerts.extend(self.check_milestones())
        
        # Runway check
        runway_alert = self.check_runway()
        if runway_alert:
            alerts.append(runway_alert)
            
        return alerts
        
    def get_cohort_analysis(self) -> Dict[str, Any]:
        """Perform cohort analysis of revenue sources."""
        sql = """
        SELECT 
            source,
            DATE_TRUNC('month', recorded_at) as cohort_month,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue,
            COUNT(DISTINCT customer_id) as customers
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '12 months'
        GROUP BY source, cohort_month
        ORDER BY cohort_month DESC, source
        """
        result = self.execute_sql(sql)
        return {"cohorts": result.get("rows", [])}
        
    def get_churn_forecast(self) -> Dict[str, Any]:
        """Forecast churn based on historical patterns."""
        sql = """
        WITH monthly_active AS (
            SELECT
                DATE_TRUNC('month', recorded_at) as month,
                COUNT(DISTINCT customer_id) as active_customers
            FROM revenue_events
            WHERE event_type = 'revenue'
            GROUP BY month
        ),
        churn_calc AS (
            SELECT
                curr.month,
                curr.active_customers,
                prev.active_customers as prev_active,
                (prev.active_customers - curr.active_customers) / prev.active_customers as churn_rate
            FROM monthly_active curr
            LEFT JOIN monthly_active prev ON curr.month = prev.month + INTERVAL '1 month'
        )
        SELECT
            AVG(churn_rate) as avg_churn_rate,
            STDDEV(churn_rate) as churn_stddev
        FROM churn_calc
        """
        result = self.execute_sql(sql)
        stats = result.get("rows", [{}])[0]
        
        # Forecast next 12 months
        forecast = []
        current_month = datetime.now().replace(day=1)
        sql = """
        SELECT COUNT(DISTINCT customer_id) as current_customers
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '30 days'
        """
        result = self.execute_sql(sql)
        current_customers = result.get("rows", [{}])[0].get("current_customers", 0)
        
        for i in range(12):
            forecast_month = (current_month + timedelta(days=30*i)).strftime("%Y-%m")
            current_customers *= (1 - stats["avg_churn_rate"])
            forecast.append({
                "month": forecast_month,
                "projected_customers": math.floor(current_customers)
            })
            
        return {
            "avg_churn_rate": stats["avg_churn_rate"],
            "churn_stddev": stats["churn_stddev"],
            "forecast": forecast
        }

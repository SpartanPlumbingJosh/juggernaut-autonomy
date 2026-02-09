"""
Automated revenue tracking system with forecasting and alerts.
Calculates runway to targets and analyzes trends.
"""
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import statistics

TARGET_REVENUE = 16_000_000  # $16M ARR target
DAILY_MONITOR_INTERVAL = timedelta(days=1)
ALERT_THRESHOLD = 0.15  # 15% deviation triggers alert
MIN_SIGNIFICANT_CHANGE = 0.05  # 5% minimum meaningful change

class RevenueTracker:
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.last_run = None

    async def run_daily_check(self) -> Dict[str, any]:
        """Execute daily revenue monitoring pipeline."""
        self.last_run = datetime.now(timezone.utc)
        
        # Get revenue data
        current = await self._get_current_metrics()
        history = await self._get_historic_daily_revenue(days=90)
        
        # Perform analysis
        analysis = {
            "current": current,
            "runway": self._calculate_runway(current["revenue_cents"], current["growth_rate"]),
            "forecast": self._calculate_forecast(history),
            "milestones": self._check_milestones(current["revenue_cents"]),
            "anomalies": self._detect_anomalies(history),
        }
        
        # Check for alerts
        alerts = self._generate_alerts(analysis)
        if alerts:
            await self._send_alerts(alerts)
            
        return analysis

    async def _get_current_metrics(self) -> Dict[str, any]:
        """Get current revenue and growth metrics."""
        sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '30 days'
        """
        result = await self.execute_sql(sql)
        current = result.get("rows", [{}])[0]
        
        # Calculate 30-day growth rate
        prev_sql = """
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents
        FROM revenue_events  
        WHERE recorded_at >= NOW() - INTERVAL '60 days'
          AND recorded_at <= NOW() - INTERVAL '30 days'
        """
        prev_result = await self.execute_sql(prev_sql)
        prev_revenue = prev_result.get("rows", [{}])[0].get("revenue_cents", 0) or 0
        current_revenue = current.get("revenue_cents", 0) or 0
        
        growth_rate = ((current_revenue - prev_revenue) / prev_revenue) if prev_revenue > 0 else 0
        
        return {
            "revenue_cents": current_revenue,
            "transaction_count": current.get("transaction_count", 0),
            "growth_rate": growth_rate,
            "monitored_at": self.last_run.isoformat()
        }

    async def _get_historic_daily_revenue(self, days: int) -> List[Dict[str, any]]:
        """Get daily revenue history."""
        sql = f"""
        SELECT 
            DATE(recorded_at) as date,
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        GROUP BY DATE(recorded_at)
        ORDER BY date ASC
        """
        result = await self.execute_sql(sql)
        return result.get("rows", [])

    def _calculate_runway(self, current_revenue: float, growth_rate: float) -> Dict[str, any]:
        """Calculate days remaining to hit target revenue."""
        if current_revenue <= 0 or growth_rate <= 0:
            return {"days": float('inf'), "date": None, "achievable": False}
            
        days = 0
        projected = current_revenue
        
        while projected < TARGET_REVENUE * 100:  # Convert dollars to cents
            days += 1
            projected *= (1 + growth_rate)
            
            if days > 365 * 5:  # Cap at 5 years
                return {"days": float('inf'), "date": None, "achievable": False}
                
        target_date = self.last_run + timedelta(days=days)
        return {
            "days": days,
            "date": target_date.isoformat(),
            "achievable": True,
            "current_revenue": current_revenue,
            "required_growth": growth_rate
        }

    def _calculate_forecast(self, history: List[Dict[str, any]]) -> Dict[str, any]:
        """Generate revenue forecast using multiple methods."""
        if len(history) < 14:  # Need at least 2 weeks of data
            return {}
            
        # Simple moving averages
        daily_values = [h["revenue_cents"] for h in history]
        weekly_values = [sum(daily_values[i:i+7]) for i in range(0, len(daily_values), 7)]
        
        # Growth rate based forecast
        growth_rates = [
            (history[i+1]["revenue_cents"] / history[i]["revenue_cents"] - 1)
            for i in range(len(history)-1)
            if history[i]["revenue_cents"] > 0
        ]
        avg_growth = statistics.mean(growth_rates) if growth_rates else 0
        
        last_value = history[-1]["revenue_cents"]
        forecast_values = [
            last_value * (1 + avg_growth) ** day 
            for day in range(1, 31)  # 30 day forecast
        ]
        
        return {
            "method": "exponential_growth",
            "growth_rate": avg_growth,
            "projection": forecast_values,
            "confidence": 0.8 if len(history) > 30 else 0.5
        }

    def _check_milestones(self, current_revenue: float) -> Dict[str, any]:
        """Check progress against key revenue milestones."""
        milestones = {
            "100k": 100_000 * 100,  # $100K in cents
            "250k": 250_000 * 100,
            "500k": 500_000 * 100,
            "1m": 1_000_000 * 100,
            "5m": 5_000_000 * 100,
            "10m": 10_000_000 * 100,
            "16m": TARGET_REVENUE * 100
        }
        
        results = {}
        for name, target in milestones.items():
            progress = min(current_revenue / target, 1.0)
            remaining = max(target - current_revenue, 0)
            results[name] = {
                "achieved": current_revenue >= target,
                "progress": progress,
                "remaining_cents": remaining,
                "target_cents": target
            }
            
        return results

    def _detect_anomalies(self, history: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Detect statistically significant changes in revenue patterns."""
        if len(history) < 14:
            return []
            
        values = [h["revenue_cents"] for h in history]
        moving_avg = statistics.mean(values[-7:])  # 7-day moving average
        stdev = statistics.stdev(values[-14:]) if len(values) >= 14 else 0
            
        anomalies = []
        threshold = moving_avg * ALERT_THRESHOLD
        
        for day in history[-7:]:  # Check last 7 days
            delta = abs(day["revenue_cents"] - moving_avg)
            if delta > threshold and delta > moving_avg * MIN_SIGNIFICANT_CHANGE:
                anomalies.append({
                    "date": day["date"],
                    "value": day["revenue_cents"],
                    "expected": moving_avg,
                    "deviation": delta / moving_avg,
                    "severity": min(delta / (stdev or 1), 5.0)  # Cap at 5x severity
                })
                
        return anomalies

    def _generate_alerts(self, analysis: Dict[str, any]) -> List[str]:
        """Generate alert messages from analysis."""
        alerts = []
        
        # Milestone alerts
        for name, milestone in analysis["milestones"].items():
            if 0.9 < milestone["progress"] < 1.0:  # Approaching milestone
                alerts.append(
                    f"Approaching {name.upper()} revenue milestone "
                    f"({milestone['progress']*100:.1f}% complete)"
                )
        
        # Runway alerts
        runway = analysis["runway"]
        if not runway["achievable"]:
            alerts.append("Current growth rate is insufficient to reach revenue target")
        elif runway["days"] > 365 * 2:
            alerts.append(f"Long runway to target: {runway['days']} days at current growth")
            
        # Anomaly alerts
        for anomaly in analysis["anomalies"]:
            alerts.append(
                f"Revenue anomaly detected on {anomaly['date']}: "
                f"{anomaly['deviation']*100:.1f}% deviation"
            )
            
        return alerts

    async def _send_alerts(self, alerts: List[str]) -> None:
        """Send alert notifications."""
        for alert in alerts:
            await self.log_action(
                "revenue.alert",
                alert,
                level="warning",
                alert_data={"last_run": self.last_run.isoformat()}
            )

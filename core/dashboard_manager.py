from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import math

class DashboardManager:
    """Manages real-time revenue dashboard and alerts."""
    
    def __init__(self):
        self.target_cents = 1000000000  # $10M
        self.milestones = [0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
        self.last_alerted_milestone = -1
        self.anomaly_threshold_multiplier = 3
        
    def calculate_progress(self, current_cents: int) -> Dict[str, Any]:
        """Calculate progress toward target."""
        progress = min(current_cents / self.target_cents, 1.0)
        next_milestone = next((m for m in self.milestones if m > progress), None)
        
        return {
            "progress": progress,
            "next_milestone": next_milestone,
            "target_cents": self.target_cents,
            "current_cents": current_cents
        }
    
    def check_milestone_alerts(self, current_cents: int) -> Optional[Dict[str, Any]]:
        """Check if we've crossed any milestones."""
        progress = current_cents / self.target_cents
        crossed = [m for m in self.milestones 
                  if m <= progress and m > self.last_alerted_milestone]
        
        if crossed:
            self.last_alerted_milestone = max(crossed)
            return {
                "milestone": self.last_alerted_milestone,
                "current_cents": current_cents,
                "timestamp": datetime.utcnow().isoformat()
            }
        return None
    
    def analyze_growth(self, revenue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze revenue growth patterns."""
        first_revenue = revenue_data.get("first_revenue_at")
        last_revenue = revenue_data.get("last_revenue_at")
        total_revenue = revenue_data.get("current_cents", 0)
        
        if not first_revenue or not last_revenue:
            return {}
            
        days = (last_revenue - first_revenue).days or 1
        growth_rate = total_revenue / days
        
        # Projected completion date
        remaining = self.target_cents - total_revenue
        days_to_target = math.ceil(remaining / growth_rate) if growth_rate > 0 else None
        projected_date = (last_revenue + timedelta(days=days_to_target)) if days_to_target else None
        
        return {
            "growth_rate_cents_per_day": growth_rate,
            "projected_completion_date": projected_date,
            "days_to_target": days_to_target
        }
    
    def detect_anomalies(self, transactions: Dict[str, Any]) -> Dict[str, Any]:
        """Detect anomalous revenue events."""
        if not transactions:
            return {}
            
        amounts = [t.get("amount_cents", 0) for t in transactions]
        mean = sum(amounts) / len(amounts) if amounts else 0
        stddev = math.sqrt(sum((x - mean) ** 2 for x in amounts) / len(amounts)) if amounts else 0
        
        threshold = mean + self.anomaly_threshold_multiplier * stddev
        anomalies = [t for t in transactions if t.get("amount_cents", 0) > threshold]
        
        return {
            "anomaly_threshold_cents": threshold,
            "anomalies_detected": len(anomalies),
            "mean_cents": mean,
            "stddev_cents": stddev
        }

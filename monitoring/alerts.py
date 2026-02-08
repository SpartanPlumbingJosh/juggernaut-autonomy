import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
from scipy import stats
from core.database import query_db

class RevenueMonitor:
    """
    Real-time revenue monitoring with anomaly detection and alerting.
    Designed for 99.9% uptime SLA during Q1 2026.
    """
    
    def __init__(self):
        self.baseline_window = timedelta(days=14)
        self.alert_threshold = 3.0  # 3 standard deviations
        self.min_samples = 100
    
    async def check_downtime(self) -> Optional[Dict[str, Any]]:
        """Check for revenue system downtime"""
        res = await query_db("""
            SELECT COUNT(*) as count FROM revenue_events 
            WHERE recorded_at > NOW() - INTERVAL '10 minutes'
        """)
        recent_count = res.get("rows", [{}])[0].get("count", 0)
        
        if recent_count == 0:
            return {
                "alert": "NO_RECENT_REVENUE_EVENTS",
                "severity": "critical",
                "message": "No revenue events recorded in last 10 minutes"
            }
        return None
    
    async def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect abnormal revenue patterns"""
        alerts = []
        
        # Get recent hourly revenue data
        res = await query_db("""
            SELECT 
                DATE_TRUNC('hour', recorded_at) as hour,
                SUM(amount_cents) as revenue_cents
            FROM revenue_events
            WHERE recorded_at > NOW() - INTERVAL '24 hours'
              AND event_type = 'revenue'
            GROUP BY hour
            ORDER BY hour
        """)
        hourly_data = res.get("rows", [])
        
        if len(hourly_data) < self.min_samples:
            return alerts
            
        # Get baseline data
        baseline_res = await query_db(f"""
            SELECT 
                DATE_TRUNC('hour', recorded_at) as hour,
                SUM(amount_cents) as revenue_cents
            FROM revenue_events
            WHERE recorded_at > NOW() - INTERVAL '{self.baseline_window.days} days'
              AND event_type = 'revenue'
            GROUP BY hour
        """)
        baseline = [r["revenue_cents"] for r in baseline_res.get("rows", [])]
        
        if not baseline:
            return alerts
            
        # Calculate z-scores for recent data
        baseline_mean = np.mean(baseline)
        baseline_std = np.std(baseline)
        
        for row in hourly_data[-6:]:  # Check last 6 hours
            z_score = (row["revenue_cents"] - baseline_mean) / baseline_std
            if abs(z_score) >= self.alert_threshold:
                alerts.append({
                    "alert": "REVENUE_ANOMALY",
                    "severity": "high" if abs(z_score) < 5 else "critical",
                    "hour": row["hour"].isoformat(),
                    "revenue_cents": row["revenue_cents"],
                    "z_score": z_score,
                    "message": f"Revenue anomaly detected ({z_score:.1f}σ)"
                })
        
        return alerts

    async def run_checks(self) -> List[Dict[str, Any]]:
        """Run all monitoring checks and return alerts"""
        alerts = []
        
        # Check for downtime
        downtime_alert = await self.check_downtime()
        if downtime_alert:
            alerts.append(downtime_alert)
        
        # Check for anomalies
        alerts.extend(await self.detect_anomalies())
        return alerts

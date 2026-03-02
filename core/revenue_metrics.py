from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import math
import numpy as np
from scipy.stats import linregress

# Quarterly revenue targets (in dollars)
QUARTERLY_TARGETS = {
    1: 2_500_000,  # Q1
    2: 3_000_000,  # Q2
    3: 3_500_000,  # Q3
    4: 3_000_000,  # Q4
}

ALERT_THRESHOLDS = {
    "warning": 0.9,  # 90% of target
    "critical": 0.8  # 80% of target
}

def calculate_quarterly_metrics(revenue_data: List[Dict]) -> Dict:
    """Calculate quarterly revenue metrics and compare against targets."""
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    target = QUARTERLY_TARGETS.get(quarter, 0)
    
    # Calculate actual revenue
    quarter_start = now.replace(month=(quarter-1)*3+1, day=1, hour=0, minute=0, second=0, microsecond=0)
    quarter_revenue = sum(
        r.get("amount_cents", 0) / 100 
        for r in revenue_data 
        if r.get("event_type") == "revenue" and 
        datetime.fromisoformat(r.get("recorded_at")) >= quarter_start
    )
    
    # Calculate progress
    days_in_quarter = (now - quarter_start).days
    expected_progress = days_in_quarter / 90  # Approximate days in quarter
    actual_progress = quarter_revenue / target if target else 0
    
    # Determine alert status
    alert = None
    if actual_progress < ALERT_THRESHOLDS["critical"]:
        alert = "critical"
    elif actual_progress < ALERT_THRESHOLDS["warning"]:
        alert = "warning"
    
    return {
        "quarter": quarter,
        "target": target,
        "actual": quarter_revenue,
        "progress": actual_progress,
        "expected_progress": expected_progress,
        "alert": alert
    }

def calculate_projection(revenue_data: List[Dict]) -> Dict:
    """Calculate revenue projections toward $12M annual goal."""
    # Convert revenue data to daily totals
    daily_totals = {}
    for r in revenue_data:
        if r.get("event_type") == "revenue":
            date = datetime.fromisoformat(r.get("recorded_at")).date()
            amount = r.get("amount_cents", 0) / 100
            daily_totals[date] = daily_totals.get(date, 0) + amount
    
    # Create time series
    dates = sorted(daily_totals.keys())
    days_since_start = [(d - dates[0]).days for d in dates]
    revenues = [daily_totals[d] for d in dates]
    
    # Linear regression for projection
    slope, intercept, _, _, _ = linregress(days_since_start, revenues)
    
    # Project annual revenue
    days_in_year = 365
    projected_annual = intercept + slope * days_in_year
    
    # Calculate trajectory toward $12M goal
    goal = 12_000_000
    trajectory = projected_annual / goal
    
    # Calculate required growth rate
    current_annualized = sum(revenues) * (365 / len(dates))
    required_growth = (goal - current_annualized) / max(1, (365 - len(dates)))
    
    return {
        "projected_annual": projected_annual,
        "trajectory": trajectory,
        "required_daily_growth": required_growth,
        "current_annualized": current_annualized
    }

def generate_metrics_report(revenue_data: List[Dict]) -> Dict:
    """Generate comprehensive revenue metrics report."""
    quarterly = calculate_quarterly_metrics(revenue_data)
    projection = calculate_projection(revenue_data)
    
    return {
        "quarterly": quarterly,
        "projection": projection,
        "timestamp": datetime.now().isoformat(),
        "status": "ok" if quarterly.get("alert") is None else quarterly.get("alert")
    }

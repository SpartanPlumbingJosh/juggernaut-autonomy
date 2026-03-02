"""
Revenue Monitoring System - Track MRR, ARR, churn and progress toward $10M goal.
Includes forecasting and alerting capabilities.
"""

from datetime import datetime, timedelta
import math
from typing import Dict, List, Optional
import numpy as np
from scipy.stats import linregress

# Constants
TARGET_ARR_CENTS = 10_000_000_00  # $10M in cents
ALERT_THRESHOLDS = [0.25, 0.5, 0.75, 1.0]  # Milestone percentages of target
ANOMALY_THRESHOLD = 2.0  # Standard deviations for anomaly detection

async def calculate_mrr(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate Monthly Recurring Revenue."""
    sql = """
    SELECT 
        SUM(amount_cents) as mrr_cents,
        COUNT(DISTINCT customer_id) as active_customers
    FROM revenue_events
    WHERE event_type = 'revenue'
      AND recorded_at >= NOW() - INTERVAL '1 month'
      AND is_recurring = TRUE
    """
    result = await execute_sql(sql)
    return result.get("rows", [{}])[0]

async def calculate_arr(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate Annual Recurring Revenue."""
    sql = """
    SELECT 
        SUM(amount_cents) * 12 as arr_cents,
        COUNT(DISTINCT customer_id) as active_customers
    FROM revenue_events
    WHERE event_type = 'revenue'
      AND recorded_at >= NOW() - INTERVAL '1 year'
      AND is_recurring = TRUE
    """
    result = await execute_sql(sql)
    return result.get("rows", [{}])[0]

async def calculate_churn(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate churn rate."""
    # Get customers who left in last month
    sql = """
    WITH lost_customers AS (
        SELECT DISTINCT customer_id
        FROM revenue_events
        WHERE event_type = 'revenue'
          AND recorded_at < NOW() - INTERVAL '1 month'
          AND recorded_at >= NOW() - INTERVAL '2 months'
        EXCEPT
        SELECT DISTINCT customer_id
        FROM revenue_events
        WHERE event_type = 'revenue'
          AND recorded_at >= NOW() - INTERVAL '1 month'
    )
    SELECT COUNT(*) as churned_customers
    FROM lost_customers
    """
    churn_result = await execute_sql(sql)
    churned = churn_result.get("rows", [{}])[0].get("churned_customers", 0)
    
    # Get total customers at start of period
    sql = """
    SELECT COUNT(DISTINCT customer_id) as total_customers
    FROM revenue_events
    WHERE event_type = 'revenue'
      AND recorded_at < NOW() - INTERVAL '1 month'
      AND recorded_at >= NOW() - INTERVAL '2 months'
    """
    total_result = await execute_sql(sql)
    total = total_result.get("rows", [{}])[0].get("total_customers", 1)
    
    return {
        "churn_rate": churned / total if total > 0 else 0,
        "churned_customers": churned,
        "total_customers": total
    }

async def forecast_year_end(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Forecast year-end performance using linear regression."""
    # Get daily revenue for last 90 days
    sql = """
    SELECT 
        DATE(recorded_at) as date,
        SUM(amount_cents) as revenue_cents
    FROM revenue_events
    WHERE event_type = 'revenue'
      AND recorded_at >= NOW() - INTERVAL '90 days'
    GROUP BY DATE(recorded_at)
    ORDER BY date ASC
    """
    result = await execute_sql(sql)
    data = result.get("rows", [])
    
    if not data:
        return {"forecast_arr_cents": 0, "confidence": 0}
    
    # Prepare data for regression
    dates = [datetime.strptime(row['date'], '%Y-%m-%d') for row in data]
    days_since_start = [(d - dates[0]).days for d in dates]
    revenues = [row['revenue_cents'] for row in data]
    
    # Perform linear regression
    slope, intercept, r_value, p_value, std_err = linregress(days_since_start, revenues)
    
    # Forecast to end of year
    days_remaining = (datetime(dates[-1].year, 12, 31) - dates[-1]).days
    forecast_daily = slope * (days_since_start[-1] + days_remaining) + intercept
    forecast_arr = forecast_daily * 365
    
    return {
        "forecast_arr_cents": max(0, forecast_arr),
        "confidence": r_value ** 2,
        "current_trajectory_cents": slope * 365
    }

async def check_milestones_and_anomalies(execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]) -> Dict[str, Any]:
    """Check for revenue milestones and anomalies."""
    arr_result = await calculate_arr(execute_sql)
    arr_cents = arr_result.get("arr_cents", 0)
    
    # Check milestones
    for threshold in ALERT_THRESHOLDS:
        milestone = TARGET_ARR_CENTS * threshold
        if arr_cents >= milestone and arr_cents < milestone * 1.01:  # Within 1% of milestone
            log_action(
                "revenue.milestone_reached",
                f"Revenue milestone reached: ${milestone/100:.2f}",
                level="info",
                output_data={
                    "milestone_cents": milestone,
                    "current_arr_cents": arr_cents
                }
            )
    
    # Check for anomalies
    forecast = await forecast_year_end(execute_sql)
    forecast_arr = forecast.get("forecast_arr_cents", 0)
    if forecast_arr > 0:
        deviation = abs(arr_cents - forecast_arr) / forecast_arr
        if deviation > ANOMALY_THRESHOLD:
            log_action(
                "revenue.anomaly_detected",
                f"Revenue anomaly detected: {deviation:.2f} standard deviations from forecast",
                level="warning",
                output_data={
                    "current_arr_cents": arr_cents,
                    "forecast_arr_cents": forecast_arr,
                    "deviation": deviation
                }
            )
    
    return {
        "arr_cents": arr_cents,
        "target_arr_cents": TARGET_ARR_CENTS,
        "progress_ratio": arr_cents / TARGET_ARR_CENTS if TARGET_ARR_CENTS > 0 else 0
    }

async def get_revenue_monitoring_summary(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Get comprehensive revenue monitoring summary."""
    mrr = await calculate_mrr(execute_sql)
    arr = await calculate_arr(execute_sql)
    churn = await calculate_churn(execute_sql)
    forecast = await forecast_year_end(execute_sql)
    progress = await check_milestones_and_anomalies(execute_sql)
    
    return {
        "mrr_cents": mrr.get("mrr_cents", 0),
        "arr_cents": arr.get("arr_cents", 0),
        "churn_rate": churn.get("churn_rate", 0),
        "forecast_arr_cents": forecast.get("forecast_arr_cents", 0),
        "confidence": forecast.get("confidence", 0),
        "current_trajectory_cents": forecast.get("current_trajectory_cents", 0),
        "target_arr_cents": TARGET_ARR_CENTS,
        "progress_ratio": progress.get("progress_ratio", 0),
        "active_customers": arr.get("active_customers", 0),
        "churned_customers": churn.get("churned_customers", 0)
    }

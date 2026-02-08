"""
Daily revenue monitoring cron job.
Checks key metrics and sends alerts if thresholds are breached.
"""

import json
from datetime import datetime, timedelta
from core.database import query_db

def check_daily_revenue():
    """Check daily revenue against targets."""
    try:
        # Get yesterday's revenue
        yesterday = datetime.now() - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        sql = f"""
        SELECT 
            SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
            SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents,
            COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
        FROM revenue_events
        WHERE recorded_at >= '{start.isoformat()}'
          AND recorded_at < '{end.isoformat()}'
        """
        
        result = query_db(sql)
        data = result.get("rows", [{}])[0]
        
        # Check against thresholds
        daily_target = 5000000  # $50,000 daily target
        revenue = data.get("revenue_cents") or 0
        
        if revenue < daily_target * 0.8:
            print(f"ALERT: Daily revenue below target: {revenue/100} (target: {daily_target/100})")
            
        return {
            "success": True,
            "revenue_cents": revenue,
            "cost_cents": data.get("cost_cents") or 0,
            "transaction_count": data.get("transaction_count") or 0
        }
        
    except Exception as e:
        print(f"ERROR: Failed to check daily revenue: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    check_daily_revenue()

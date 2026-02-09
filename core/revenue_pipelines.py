from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)

class RevenuePipeline:
    """Base class for revenue generation pipelines"""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def track_revenue_event(self, event_type: str, amount_cents: int, source: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Record a revenue or cost event"""
        try:
            metadata_json = json.dumps(metadata or {})
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    'USD',
                    '{source}',
                    '{metadata_json}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            return True
        except Exception as e:
            logger.error(f"Failed to track revenue event: {str(e)}")
            return False

class AffiliatePipeline(RevenuePipeline):
    """Automated affiliate link integration pipeline"""
    
    def process_affiliate_links(self, links: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process and track affiliate link clicks"""
        success_count = 0
        for link in links:
            if self.track_revenue_event(
                event_type="revenue",
                amount_cents=int(link.get("commission_cents", 0)),
                source="affiliate",
                metadata={
                    "product": link.get("product"),
                    "platform": link.get("platform"),
                    "click_id": link.get("click_id")
                }
            ):
                success_count += 1
                
        return {
            "success": True,
            "processed": len(links),
            "successful": success_count
        }

class ContentPipeline(RevenuePipeline):
    """Automated content generation and publishing pipeline"""
    
    def track_content_revenue(self, content_id: str, revenue_cents: int, source: str) -> bool:
        """Track revenue from published content"""
        return self.track_revenue_event(
            event_type="revenue",
            amount_cents=revenue_cents,
            source=source,
            metadata={
                "content_id": content_id,
                "type": "content"
            }
        )

class WebhookPipeline(RevenuePipeline):
    """Payment processing webhook integration"""
    
    def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment webhook events"""
        event_type = payload.get("event_type", "unknown")
        amount_cents = int(payload.get("amount_cents", 0))
        source = payload.get("source", "webhook")
        
        success = self.track_revenue_event(
            event_type=event_type,
            amount_cents=amount_cents,
            source=source,
            metadata=payload.get("metadata")
        )
        
        return {
            "success": success,
            "event_type": event_type,
            "amount_cents": amount_cents
        }

class MonitoringDashboard:
    """Revenue monitoring and alerting system"""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    def get_revenue_summary(self, period_days: int = 30) -> Dict[str, Any]:
        """Get revenue summary for monitoring"""
        try:
            res = self.execute_sql(f"""
                SELECT 
                    SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents,
                    SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as cost_cents,
                    COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
                FROM revenue_events
                WHERE recorded_at >= NOW() - INTERVAL '{period_days} days'
            """)
            return res.get("rows", [{}])[0] or {}
        except Exception as e:
            logger.error(f"Failed to get revenue summary: {str(e)}")
            return {}

    def check_anomalies(self, threshold_pct: float = 20.0) -> Dict[str, Any]:
        """Check for revenue anomalies"""
        try:
            # Get last 7 days vs previous 7 days
            res = self.execute_sql("""
                WITH current_week AS (
                    SELECT 
                        SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents
                    FROM revenue_events
                    WHERE recorded_at >= NOW() - INTERVAL '7 days'
                ),
                previous_week AS (
                    SELECT 
                        SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as revenue_cents
                    FROM revenue_events
                    WHERE recorded_at >= NOW() - INTERVAL '14 days'
                      AND recorded_at < NOW() - INTERVAL '7 days'
                )
                SELECT 
                    cw.revenue_cents as current_week,
                    pw.revenue_cents as previous_week,
                    (cw.revenue_cents - pw.revenue_cents) / NULLIF(pw.revenue_cents, 0) * 100 as pct_change
                FROM current_week cw, previous_week pw
            """)
            data = res.get("rows", [{}])[0] or {}
            
            pct_change = float(data.get("pct_change", 0))
            anomaly = abs(pct_change) >= threshold_pct
            
            return {
                "anomaly": anomaly,
                "pct_change": pct_change,
                "current_week": data.get("current_week"),
                "previous_week": data.get("previous_week")
            }
        except Exception as e:
            logger.error(f"Failed to check anomalies: {str(e)}")
            return {"error": str(e)}

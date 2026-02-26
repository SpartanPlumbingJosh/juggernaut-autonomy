from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from core.database import query_db

class MarketingAutomation:
    """Automated sales and marketing pipeline management."""
    
    def __init__(self):
        self.channels = ["email", "seo", "social", "paid"]
        self.ab_testing_framework = ABTestingFramework()
        
    async def track_conversion(self, event_type: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Track marketing conversions and calculate CAC."""
        try:
            # Calculate CAC based on campaign spend and conversions
            campaign_id = metadata.get("campaign_id")
            if not campaign_id:
                return {"success": False, "error": "Missing campaign_id"}
                
            # Get campaign spend
            spend_sql = f"""
                SELECT SUM(amount_cents) as total_spent
                FROM marketing_spend
                WHERE campaign_id = '{campaign_id}'
            """
            spend_result = await query_db(spend_sql)
            total_spent = (spend_result.get("rows", [{}])[0] or {}).get("total_spent", 0)
            
            # Get conversions
            conv_sql = f"""
                SELECT COUNT(*) as conversions
                FROM marketing_conversions
                WHERE campaign_id = '{campaign_id}'
            """
            conv_result = await query_db(conv_sql)
            conversions = (conv_result.get("rows", [{}])[0] or {}).get("conversions", 0)
            
            cac = (total_spent / conversions) if conversions > 0 else 0
            
            # Record conversion event
            insert_sql = f"""
                INSERT INTO marketing_conversions (
                    id, campaign_id, event_type, metadata, 
                    recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{campaign_id}',
                    '{event_type}',
                    '{json.dumps(metadata)}',
                    NOW(),
                    NOW()
                )
            """
            await query_db(insert_sql)
            
            return {
                "success": True,
                "cac": cac,
                "conversions": conversions,
                "total_spent": total_spent
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def optimize_channel_performance(self) -> Dict[str, Any]:
        """Automatically optimize marketing channel performance."""
        results = {}
        for channel in self.channels:
            # Get channel performance metrics
            perf_sql = f"""
                SELECT 
                    SUM(amount_cents) as total_spent,
                    COUNT(*) as conversions,
                    SUM(amount_cents) / NULLIF(COUNT(*), 0) as cac
                FROM marketing_spend ms
                JOIN marketing_conversions mc ON ms.campaign_id = mc.campaign_id
                WHERE channel = '{channel}'
                AND recorded_at >= NOW() - INTERVAL '30 days'
            """
            perf_result = await query_db(perf_sql)
            row = perf_result.get("rows", [{}])[0] or {}
            
            # Run A/B tests to optimize
            ab_results = await self.ab_testing_framework.run_tests_for_channel(channel)
            
            results[channel] = {
                "total_spent": row.get("total_spent", 0),
                "conversions": row.get("conversions", 0),
                "cac": row.get("cac", 0),
                "ab_tests": ab_results
            }
            
        return {"success": True, "results": results}

class ABTestingFramework:
    """A/B testing framework for marketing optimization."""
    
    async def run_tests_for_channel(self, channel: str) -> Dict[str, Any]:
        """Run A/B tests for a specific marketing channel."""
        # Get active tests for channel
        tests_sql = f"""
            SELECT id, test_type, variants, goal_metric
            FROM marketing_ab_tests
            WHERE channel = '{channel}'
            AND status = 'active'
        """
        tests_result = await query_db(tests_sql)
        tests = tests_result.get("rows", [])
        
        results = []
        for test in tests:
            test_id = test.get("id")
            test_type = test.get("test_type")
            variants = test.get("variants", [])
            goal_metric = test.get("goal_metric")
            
            # Run test and evaluate results
            test_result = await self.evaluate_test(test_id, test_type, variants, goal_metric)
            results.append(test_result)
            
        return results
        
    async def evaluate_test(self, test_id: str, test_type: str, variants: List[str], goal_metric: str) -> Dict[str, Any]:
        """Evaluate A/B test results and determine winning variant."""
        # Get performance data for each variant
        perf_sql = f"""
            SELECT variant, COUNT(*) as conversions, SUM(amount_cents) as revenue
            FROM marketing_test_results
            WHERE test_id = '{test_id}'
            GROUP BY variant
        """
        perf_result = await query_db(perf_sql)
        variant_perf = {row["variant"]: row for row in perf_result.get("rows", [])}
        
        # Determine winner based on goal metric
        winner = None
        best_value = 0
        for variant in variants:
            perf = variant_perf.get(variant, {})
            value = perf.get(goal_metric, 0)
            if value > best_value:
                best_value = value
                winner = variant
                
        return {
            "test_id": test_id,
            "winner": winner,
            "best_value": best_value,
            "variants": variant_perf
        }

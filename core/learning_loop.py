"""
Learning Loop - Close the feedback cycle between experiments and discovery.

When experiments complete, this module:
1. Analyzes results (success/failure, ROI, patterns)
2. Updates discovery weights for opportunity types
3. Stores success patterns for future use
4. Adjusts scoring algorithms based on outcomes

This closes the L4 → L5 gap: System learns from successes, not just failures.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from decimal import Decimal


def update_discovery_weights(
    execute_sql,
    log_action,
    opportunity_type: str,
    category: str,
    roi: float,
    success: bool
) -> Dict[str, Any]:
    """
    Update discovery weights based on experiment outcomes.
    
    Args:
        execute_sql: Database query function
        log_action: Logging function
        opportunity_type: Type of opportunity (e.g., "api_integration", "content_creation")
        category: Category (e.g., "automation", "marketplace")
        roi: Return on investment (percentage)
        success: Whether experiment was successful
    
    Returns:
        Dict with update results
    """
    try:
        if success and roi > 200:
            weight_adjustment = 0.2
        elif success and roi > 100:
            weight_adjustment = 0.1
        elif success and roi > 0:
            weight_adjustment = 0.05
        elif not success:
            weight_adjustment = -0.1
        else:
            weight_adjustment = 0.0
        
        ensure_weights_table_sql = """
        CREATE TABLE IF NOT EXISTS discovery_weights (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            opportunity_type VARCHAR(100) NOT NULL,
            category VARCHAR(100),
            weight DECIMAL(5,3) DEFAULT 1.0,
            sample_count INTEGER DEFAULT 0,
            total_roi DECIMAL(10,2) DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(opportunity_type, category)
        );
        """
        execute_sql(ensure_weights_table_sql)
        
        safe_type = str(opportunity_type).replace("'", "''")
        safe_category = str(category).replace("'", "''")
        
        upsert_sql = f"""
        INSERT INTO discovery_weights (
            opportunity_type, 
            category, 
            weight, 
            sample_count,
            total_roi,
            success_count,
            failure_count,
            last_updated
        ) VALUES (
            '{safe_type}',
            '{safe_category}',
            {1.0 + weight_adjustment},
            1,
            {roi},
            {1 if success else 0},
            {0 if success else 1},
            NOW()
        )
        ON CONFLICT (opportunity_type, category) 
        DO UPDATE SET
            weight = GREATEST(0.1, LEAST(2.0, discovery_weights.weight + {weight_adjustment})),
            sample_count = discovery_weights.sample_count + 1,
            total_roi = discovery_weights.total_roi + {roi},
            success_count = discovery_weights.success_count + {1 if success else 0},
            failure_count = discovery_weights.failure_count + {0 if success else 1},
            last_updated = NOW()
        RETURNING weight, sample_count, total_roi, success_count, failure_count;
        """
        
        result = execute_sql(upsert_sql)
        rows = result.get("rows", [])
        
        if rows:
            updated = rows[0]
            log_action(
                "learning.weight_updated",
                f"Updated discovery weight for {opportunity_type}/{category}",
                level="info",
                output_data={
                    "opportunity_type": opportunity_type,
                    "category": category,
                    "new_weight": float(updated.get("weight", 1.0)),
                    "sample_count": updated.get("sample_count", 0),
                    "avg_roi": float(updated.get("total_roi", 0)) / max(1, updated.get("sample_count", 1)),
                    "success_rate": updated.get("success_count", 0) / max(1, updated.get("sample_count", 1))
                }
            )
            
            return {
                "success": True,
                "weight": float(updated.get("weight", 1.0)),
                "sample_count": updated.get("sample_count", 0)
            }
        
        return {"success": False, "error": "No rows returned"}
        
    except Exception as e:
        log_action(
            "learning.weight_update_failed",
            f"Failed to update discovery weight: {str(e)}",
            level="error",
            error_data={"error": str(e)}
        )
        return {"success": False, "error": str(e)}


def store_success_pattern(
    execute_sql,
    log_action,
    experiment_id: str,
    opportunity_type: str,
    features: Dict[str, Any],
    roi: float,
    revenue_generated: float
) -> Dict[str, Any]:
    """
    Store successful experiment patterns for future reference.
    """
    try:
        ensure_patterns_table_sql = """
        CREATE TABLE IF NOT EXISTS success_patterns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            experiment_id UUID,
            opportunity_type VARCHAR(100),
            features JSONB,
            roi DECIMAL(10,2),
            revenue_generated DECIMAL(10,2),
            pattern_hash VARCHAR(64),
            occurrence_count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW(),
            last_seen TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_success_patterns_type 
        ON success_patterns(opportunity_type);
        
        CREATE INDEX IF NOT EXISTS idx_success_patterns_roi 
        ON success_patterns(roi DESC);
        """
        execute_sql(ensure_patterns_table_sql)
        
        import hashlib
        features_str = json.dumps(features, sort_keys=True)
        pattern_hash = hashlib.sha256(features_str.encode()).hexdigest()
        
        features_json = json.dumps(features).replace("'", "''")
        
        insert_sql = f"""
        INSERT INTO success_patterns (
            experiment_id,
            opportunity_type,
            features,
            roi,
            revenue_generated,
            pattern_hash,
            created_at,
            last_seen
        ) VALUES (
            '{experiment_id}',
            '{str(opportunity_type).replace("'", "''")}',
            '{features_json}'::jsonb,
            {roi},
            {revenue_generated},
            '{pattern_hash}',
            NOW(),
            NOW()
        )
        ON CONFLICT (pattern_hash)
        DO UPDATE SET
            occurrence_count = success_patterns.occurrence_count + 1,
            last_seen = NOW()
        RETURNING id, occurrence_count;
        """
        
        result = execute_sql(insert_sql)
        rows = result.get("rows", [])
        
        if rows:
            pattern = rows[0]
            log_action(
                "learning.pattern_stored",
                f"Stored success pattern for {opportunity_type}",
                level="info",
                output_data={
                    "pattern_id": pattern.get("id"),
                    "occurrence_count": pattern.get("occurrence_count", 1),
                    "roi": roi
                }
            )
            
            return {
                "success": True,
                "pattern_id": pattern.get("id"),
                "occurrence_count": pattern.get("occurrence_count", 1)
            }
        
        return {"success": False, "error": "No rows returned"}
        
    except Exception as e:
        log_action(
            "learning.pattern_storage_failed",
            f"Failed to store success pattern: {str(e)}",
            level="error",
            error_data={"error": str(e)}
        )
        return {"success": False, "error": str(e)}


def extract_experiment_features(experiment: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key features from an experiment for pattern matching."""
    features = {}
    
    metadata = experiment.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    
    features["opportunity_type"] = experiment.get("experiment_type") or metadata.get("opportunity_type")
    features["budget_range"] = "low" if experiment.get("budget_allocated", 0) < 100 else "medium" if experiment.get("budget_allocated", 0) < 500 else "high"
    features["has_automation"] = bool(metadata.get("automation_level"))
    features["requires_api"] = bool(metadata.get("api_required"))
    features["time_to_revenue"] = metadata.get("time_to_revenue_days")
    features["complexity"] = metadata.get("complexity", "medium")
    
    return features


def on_experiment_complete(
    execute_sql,
    log_action,
    experiment_id: str,
    experiment_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Callback when an experiment completes - updates learning system.
    
    This is the main entry point for the learning loop.
    Call this from experiment completion handler.
    """
    try:
        status = experiment_data.get("status")
        roi = float(experiment_data.get("roi", 0))
        revenue_generated = float(experiment_data.get("revenue_generated", 0))
        budget_spent = float(experiment_data.get("actual_cost", 0) or experiment_data.get("budget_spent", 0))
        opportunity_type = experiment_data.get("experiment_type", "unknown")
        
        success = (
            status == "completed" and
            roi > 0 and
            revenue_generated > budget_spent
        )
        
        metadata = experiment_data.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        category = metadata.get("category", "general")
        
        results = {
            "experiment_id": experiment_id,
            "success": success,
            "roi": roi,
            "actions_taken": []
        }
        
        weight_result = update_discovery_weights(
            execute_sql,
            log_action,
            opportunity_type,
            category,
            roi,
            success
        )
        results["actions_taken"].append({
            "action": "update_weights",
            "result": weight_result
        })
        
        if success and roi > 100:
            features = extract_experiment_features(experiment_data)
            pattern_result = store_success_pattern(
                execute_sql,
                log_action,
                experiment_id,
                opportunity_type,
                features,
                roi,
                revenue_generated
            )
            results["actions_taken"].append({
                "action": "store_pattern",
                "result": pattern_result
            })
        
        details_json = json.dumps({
            "experiment_id": experiment_id,
            "opportunity_type": opportunity_type,
            "category": category,
            "roi": roi,
            "revenue": revenue_generated,
            "cost": budget_spent,
            "success": success
        }).replace("'", "''")
        
        learning_sql = f"""
        INSERT INTO learnings (
            category,
            summary,
            details,
            confidence,
            source_task_id,
            applied_count,
            created_at
        ) VALUES (
            'experiment_outcome',
            'Experiment {experiment_id[:8]} {"succeeded" if success else "failed"} with {roi:.1f}% ROI',
            '{details_json}'::jsonb,
            {0.9 if success else 0.7},
            '{experiment_id}',
            1,
            NOW()
        );
        """
        execute_sql(learning_sql)
        results["actions_taken"].append({
            "action": "create_learning",
            "result": {"success": True}
        })
        
        log_action(
            "learning.experiment_processed",
            f"Processed experiment completion: {experiment_id[:8]}",
            level="info",
            output_data=results
        )
        
        return results
        
    except Exception as e:
        log_action(
            "learning.experiment_processing_failed",
            f"Failed to process experiment completion: {str(e)}",
            level="error",
            error_data={"error": str(e), "experiment_id": experiment_id}
        )
        return {"success": False, "error": str(e)}


def get_top_patterns(
    execute_sql,
    limit: int = 10,
    min_roi: float = 100.0
) -> List[Dict[str, Any]]:
    """Get top success patterns to guide future opportunity discovery."""
    try:
        sql = f"""
        SELECT 
            opportunity_type,
            features,
            AVG(roi) as avg_roi,
            SUM(revenue_generated) as total_revenue,
            COUNT(*) as occurrence_count,
            MAX(last_seen) as last_seen
        FROM success_patterns
        WHERE roi >= {min_roi}
        GROUP BY opportunity_type, features
        ORDER BY avg_roi DESC, total_revenue DESC
        LIMIT {limit};
        """
        
        result = execute_sql(sql)
        return result.get("rows", [])
        
    except Exception:
        return []


__all__ = [
    "on_experiment_complete",
    "update_discovery_weights",
    "store_success_pattern",
    "extract_experiment_features",
    "get_top_patterns"
]

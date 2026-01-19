"""
Phase 5.1: Opportunity Scanner - Proactive Systems

This module provides market scanning, opportunity identification, scoring,
duplicate detection, and scan scheduling capabilities.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from .database import query_db, log_execution

# =============================================================================
# SCAN MANAGEMENT
# =============================================================================


def start_scan(
    scan_type: str,
    source: str,
    config: Optional[Dict] = None,
    triggered_by: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Start a new opportunity scan.
    
    Args:
        scan_type: Type of scan (market_research, competitor, trend, lead_gen, etc.)
        source: Where we're scanning (web, api, database, servicetitan, angi, etc.)
        config: Scan configuration parameters
        triggered_by: Who/what initiated the scan
        
    Returns:
        Dict with scan_id and status
    """
    scan_id = str(uuid4())
    config = config or {}
    
    result = query_db(
        """
        INSERT INTO opportunity_scans (id, scan_type, source, scan_config, triggered_by)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, scan_type, source, status, started_at
        """,
        [scan_id, scan_type, source, json.dumps(config), triggered_by]
    )
    
    log_execution(
        worker_id=triggered_by,
        action="scan.start",
        message=f"Started {scan_type} scan from {source}",
        details={"scan_id": scan_id, "config": config}
    )
    
    return {
        "success": True,
        "scan_id": scan_id,
        "scan_type": scan_type,
        "source": source,
        "status": "running"
    }


def complete_scan(
    scan_id: str,
    opportunities_found: int = 0,
    opportunities_qualified: int = 0,
    opportunities_duplicates: int = 0,
    results_summary: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Mark a scan as completed with results.
    
    Args:
        scan_id: The scan to complete
        opportunities_found: Total opportunities identified
        opportunities_qualified: Opportunities that passed scoring threshold
        opportunities_duplicates: Duplicate opportunities filtered out
        results_summary: Summary of scan results
        
    Returns:
        Dict with completion status
    """
    results_summary = results_summary or {}
    
    result = query_db(
        """
        UPDATE opportunity_scans 
        SET status = 'completed',
            completed_at = NOW(),
            opportunities_found = $2,
            opportunities_qualified = $3,
            opportunities_duplicates = $4,
            results_summary = $5
        WHERE id = $1
        RETURNING id, scan_type, source, opportunities_found, opportunities_qualified
        """,
        [scan_id, opportunities_found, opportunities_qualified, 
         opportunities_duplicates, json.dumps(results_summary)]
    )
    
    if not result.get("rows"):
        return {"success": False, "error": "Scan not found"}
    
    row = result["rows"][0]
    log_execution(
        worker_id="SCANNER",
        action="scan.complete",
        message=f"Completed scan {scan_id}: found={opportunities_found}, qualified={opportunities_qualified}",
        details={"scan_id": scan_id, "results": results_summary}
    )
    
    return {
        "success": True,
        "scan_id": scan_id,
        "opportunities_found": opportunities_found,
        "opportunities_qualified": opportunities_qualified,
        "opportunities_duplicates": opportunities_duplicates
    }


def fail_scan(scan_id: str, error_message: str) -> Dict[str, Any]:
    """
    Mark a scan as failed.
    
    Args:
        scan_id: The scan that failed
        error_message: Description of the failure
        
    Returns:
        Dict with failure status
    """
    result = query_db(
        """
        UPDATE opportunity_scans 
        SET status = 'failed', completed_at = NOW(), error_message = $2
        WHERE id = $1
        RETURNING id
        """,
        [scan_id, error_message]
    )
    
    log_execution(
        worker_id="SCANNER",
        action="scan.failed",
        message=f"Scan {scan_id} failed: {error_message}",
        level="error",
        details={"scan_id": scan_id, "error": error_message}
    )
    
    return {"success": bool(result.get("rows")), "error": error_message}


def get_scan_history(
    scan_type: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    days: int = 7,
    limit: int = 50
) -> List[Dict]:
    """
    Get recent scan history with optional filters.
    
    Args:
        scan_type: Filter by scan type
        source: Filter by source
        status: Filter by status
        days: How many days back to look
        limit: Maximum results
        
    Returns:
        List of scan records
    """
    conditions = ["started_at > NOW() - INTERVAL '%s days'" % days]
    params = []
    param_idx = 1
    
    if scan_type:
        conditions.append(f"scan_type = ${param_idx}")
        params.append(scan_type)
        param_idx += 1
    if source:
        conditions.append(f"source = ${param_idx}")
        params.append(source)
        param_idx += 1
    if status:
        conditions.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1
    
    where_clause = " AND ".join(conditions)
    
    result = query_db(
        f"""
        SELECT id, scan_type, source, status, started_at, completed_at,
               opportunities_found, opportunities_qualified, opportunities_duplicates,
               results_summary, triggered_by
        FROM opportunity_scans
        WHERE {where_clause}
        ORDER BY started_at DESC
        LIMIT {limit}
        """,
        params
    )
    
    return result.get("rows", [])


# =============================================================================
# OPPORTUNITY IDENTIFICATION
# =============================================================================


def identify_opportunity(
    opportunity_type: str,
    category: str,
    description: str,
    source_id: Optional[str] = None,
    external_id: Optional[str] = None,
    estimated_value: float = 0,
    customer_name: Optional[str] = None,
    customer_contact: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
    created_by: str = "SCANNER"
) -> Dict[str, Any]:
    """
    Create a new identified opportunity.
    
    Args:
        opportunity_type: Type (lead, upsell, cross_sell, digital_product, partnership, etc.)
        category: Category within type
        description: What the opportunity is
        source_id: Reference to opportunity_sources table
        external_id: External reference ID (e.g., ServiceTitan job ID)
        estimated_value: Estimated revenue potential
        customer_name: Customer/prospect name
        customer_contact: Contact details as JSON
        metadata: Additional data
        created_by: Who/what identified this opportunity
        
    Returns:
        Dict with opportunity_id and details
    """
    opportunity_id = str(uuid4())
    customer_contact = customer_contact or {}
    metadata = metadata or {}
    
    result = query_db(
        """
        INSERT INTO opportunities (
            id, source_id, external_id, opportunity_type, category,
            estimated_value, confidence_score, status, stage,
            customer_name, customer_contact, description, metadata, created_by
        ) VALUES (
            $1, $2, $3, $4, $5, $6, 0.5, 'new', 'identified',
            $7, $8, $9, $10, $11
        )
        RETURNING id, opportunity_type, category, estimated_value, status
        """,
        [opportunity_id, source_id, external_id, opportunity_type, category,
         estimated_value, customer_name, json.dumps(customer_contact),
         description, json.dumps(metadata), created_by]
    )
    
    log_execution(
        worker_id=created_by,
        action="opportunity.identify",
        message=f"Identified {opportunity_type} opportunity: {description[:100]}",
        details={"opportunity_id": opportunity_id, "estimated_value": estimated_value}
    )
    
    return {
        "success": True,
        "opportunity_id": opportunity_id,
        "opportunity_type": opportunity_type,
        "category": category,
        "status": "new"
    }


# =============================================================================
# OPPORTUNITY SCORING
# =============================================================================


def score_opportunity(
    opportunity_id: str,
    scoring_factors: Dict[str, float],
    model_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Score an opportunity based on multiple factors.
    
    Args:
        opportunity_id: The opportunity to score
        scoring_factors: Dict of factor_name -> score (0-1)
            Common factors: urgency, fit, value_potential, ease_of_close,
                          customer_quality, competition, timing
        model_id: Which scoring model to use (optional)
        
    Returns:
        Dict with final score and breakdown
    """
    # Default weights for each factor (can be overridden by model)
    default_weights = {
        "urgency": 0.15,
        "fit": 0.20,
        "value_potential": 0.25,
        "ease_of_close": 0.15,
        "customer_quality": 0.15,
        "timing": 0.10
    }
    
    # Calculate weighted score
    total_weight = 0
    weighted_sum = 0
    
    for factor, score in scoring_factors.items():
        weight = default_weights.get(factor, 0.1)
        weighted_sum += score * weight
        total_weight += weight
    
    # Normalize to 0-1
    final_score = weighted_sum / total_weight if total_weight > 0 else 0.5
    final_score = round(final_score, 4)
    
    # Update opportunity with score
    result = query_db(
        """
        UPDATE opportunities 
        SET confidence_score = $2,
            metadata = jsonb_set(
                COALESCE(metadata, '{}'),
                '{scoring}',
                $3::jsonb
            ),
            updated_at = NOW()
        WHERE id = $1
        RETURNING id, confidence_score, status
        """,
        [opportunity_id, final_score, json.dumps({
            "factors": scoring_factors,
            "model_id": model_id,
            "scored_at": datetime.utcnow().isoformat()
        })]
    )
    
    if not result.get("rows"):
        return {"success": False, "error": "Opportunity not found"}
    
    # Record score in history
    query_db(
        """
        INSERT INTO opportunity_scores_history (opportunity_id, score, scoring_model, factors)
        VALUES ($1, $2, $3, $4)
        """,
        [opportunity_id, final_score, model_id or "default", json.dumps(scoring_factors)]
    )
    
    log_execution(
        worker_id="SCORER",
        action="opportunity.score",
        message=f"Scored opportunity {opportunity_id}: {final_score}",
        details={"opportunity_id": opportunity_id, "score": final_score, "factors": scoring_factors}
    )
    
    return {
        "success": True,
        "opportunity_id": opportunity_id,
        "final_score": final_score,
        "factors": scoring_factors,
        "model_id": model_id
    }


def bulk_score_opportunities(
    opportunity_ids: List[str],
    scoring_function: callable = None
) -> Dict[str, Any]:
    """
    Score multiple opportunities at once.
    
    Args:
        opportunity_ids: List of opportunity IDs to score
        scoring_function: Optional custom scoring function
        
    Returns:
        Dict with scores for each opportunity
    """
    results = {}
    for opp_id in opportunity_ids:
        # Get opportunity details
        opp = query_db(
            "SELECT * FROM opportunities WHERE id = $1",
            [opp_id]
        )
        if opp.get("rows"):
            # Default scoring based on available data
            row = opp["rows"][0]
            factors = {
                "value_potential": min(1.0, float(row.get("estimated_value", 0)) / 10000),
                "urgency": 0.5,  # Default
                "fit": 0.6,  # Default
            }
            result = score_opportunity(opp_id, factors)
            results[opp_id] = result.get("final_score", 0)
    
    return {"success": True, "scores": results, "count": len(results)}


def get_top_opportunities(
    limit: int = 10,
    min_score: float = 0.5,
    status: str = "new",
    opportunity_type: Optional[str] = None
) -> List[Dict]:
    """
    Get highest-scored opportunities.
    
    Args:
        limit: Maximum results
        min_score: Minimum confidence score
        status: Filter by status
        opportunity_type: Filter by type
        
    Returns:
        List of top opportunities sorted by score
    """
    conditions = ["confidence_score >= $1", "status = $2"]
    params = [min_score, status]
    param_idx = 3
    
    if opportunity_type:
        conditions.append(f"opportunity_type = ${param_idx}")
        params.append(opportunity_type)
    
    where_clause = " AND ".join(conditions)
    
    result = query_db(
        f"""
        SELECT id, opportunity_type, category, description, 
               estimated_value, confidence_score, status, stage,
               customer_name, created_at
        FROM opportunities
        WHERE {where_clause}
        ORDER BY confidence_score DESC, estimated_value DESC
        LIMIT {limit}
        """,
        params
    )
    
    return result.get("rows", [])


# =============================================================================
# DUPLICATE DETECTION
# =============================================================================


def compute_opportunity_fingerprint(
    opportunity_type: str,
    category: str,
    description: str,
    external_id: Optional[str] = None,
    customer_name: Optional[str] = None
) -> str:
    """
    Compute a fingerprint for duplicate detection.
    
    Args:
        opportunity_type: Type of opportunity
        category: Category
        description: Description text
        external_id: External reference
        customer_name: Customer name
        
    Returns:
        SHA256 hash fingerprint
    """
    # Normalize and combine key fields
    normalized = f"{opportunity_type}|{category}|{description[:200].lower().strip()}"
    if external_id:
        normalized += f"|ext:{external_id}"
    if customer_name:
        normalized += f"|cust:{customer_name.lower().strip()}"
    
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def check_duplicate(
    opportunity_type: str,
    category: str,
    description: str,
    external_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    time_window_days: int = 30
) -> Dict[str, Any]:
    """
    Check if an opportunity is a duplicate of an existing one.
    
    Args:
        opportunity_type: Type of opportunity
        category: Category
        description: Description text
        external_id: External reference (strongest match signal)
        customer_name: Customer name
        time_window_days: Only check recent opportunities
        
    Returns:
        Dict with is_duplicate flag and matching opportunity if found
    """
    # First check by external_id (exact match)
    if external_id:
        result = query_db(
            """
            SELECT id, opportunity_type, description, status, created_at
            FROM opportunities
            WHERE external_id = $1
            AND created_at > NOW() - INTERVAL '%s days'
            """ % time_window_days,
            [external_id]
        )
        if result.get("rows"):
            return {
                "is_duplicate": True,
                "match_type": "external_id",
                "matching_opportunity": result["rows"][0]
            }
    
    # Check by fingerprint in metadata
    fingerprint = compute_opportunity_fingerprint(
        opportunity_type, category, description, external_id, customer_name
    )
    
    result = query_db(
        """
        SELECT id, opportunity_type, description, status, created_at,
               metadata->>'fingerprint' as fingerprint
        FROM opportunities
        WHERE metadata->>'fingerprint' = $1
        AND created_at > NOW() - INTERVAL '%s days'
        """ % time_window_days,
        [fingerprint]
    )
    
    if result.get("rows"):
        return {
            "is_duplicate": True,
            "match_type": "fingerprint",
            "matching_opportunity": result["rows"][0]
        }
    
    # Fuzzy match on description + customer (within same type/category)
    if customer_name:
        result = query_db(
            """
            SELECT id, opportunity_type, description, status, customer_name, created_at,
                   similarity(description, $4) as desc_sim
            FROM opportunities
            WHERE opportunity_type = $1
            AND category = $2
            AND LOWER(customer_name) = LOWER($3)
            AND created_at > NOW() - INTERVAL '%s days'
            AND similarity(description, $4) > 0.6
            ORDER BY desc_sim DESC
            LIMIT 1
            """ % time_window_days,
            [opportunity_type, category, customer_name, description[:500]]
        )
        if result.get("rows"):
            return {
                "is_duplicate": True,
                "match_type": "fuzzy_customer_description",
                "similarity": result["rows"][0].get("desc_sim"),
                "matching_opportunity": result["rows"][0]
            }
    
    return {
        "is_duplicate": False,
        "fingerprint": fingerprint
    }


def identify_opportunity_with_dedup(
    opportunity_type: str,
    category: str,
    description: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Identify an opportunity with automatic duplicate detection.
    
    Args:
        opportunity_type: Type of opportunity
        category: Category
        description: Description
        **kwargs: Additional arguments for identify_opportunity
        
    Returns:
        Dict with opportunity_id or duplicate info
    """
    # Check for duplicates first
    dup_check = check_duplicate(
        opportunity_type=opportunity_type,
        category=category,
        description=description,
        external_id=kwargs.get("external_id"),
        customer_name=kwargs.get("customer_name")
    )
    
    if dup_check["is_duplicate"]:
        log_execution(
            worker_id=kwargs.get("created_by", "SCANNER"),
            action="opportunity.duplicate",
            message=f"Duplicate opportunity detected: {description[:100]}",
            details=dup_check
        )
        return {
            "success": True,
            "is_duplicate": True,
            "matching_opportunity_id": dup_check["matching_opportunity"]["id"],
            "match_type": dup_check["match_type"]
        }
    
    # Not a duplicate - create it with fingerprint
    if "metadata" not in kwargs:
        kwargs["metadata"] = {}
    kwargs["metadata"]["fingerprint"] = dup_check["fingerprint"]
    
    result = identify_opportunity(
        opportunity_type=opportunity_type,
        category=category,
        description=description,
        **kwargs
    )
    
    result["is_duplicate"] = False
    return result


# =============================================================================
# SCAN SCHEDULING
# =============================================================================


def schedule_scan(
    name: str,
    scan_type: str,
    source: str,
    cron_expression: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    config: Optional[Dict] = None,
    priority: int = 5,
    created_by: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Schedule a recurring opportunity scan.
    
    Args:
        name: Name for this scheduled scan
        scan_type: Type of scan to run
        source: Source to scan
        cron_expression: Cron schedule (e.g., "0 */6 * * *" for every 6 hours)
        interval_seconds: Alternative: run every N seconds
        config: Scan configuration
        priority: 1-10, higher = more important
        created_by: Who scheduled this
        
    Returns:
        Dict with scheduled_task_id
    """
    from .scheduler import create_scheduled_task
    
    task_config = {
        "scan_type": scan_type,
        "source": source,
        "scan_config": config or {}
    }
    
    schedule_type = "cron" if cron_expression else "interval" if interval_seconds else None
    if not schedule_type:
        return {"success": False, "error": "Must provide cron_expression or interval_seconds"}
    
    result = create_scheduled_task(
        name=name,
        description=f"Scheduled {scan_type} scan from {source}",
        task_type="opportunity_scan",
        cron_expression=cron_expression,
        interval_seconds=interval_seconds,
        config=task_config,
        priority=priority,
        created_by=created_by
    )
    
    return result


def get_scheduled_scans() -> List[Dict]:
    """
    Get all scheduled opportunity scans.
    
    Returns:
        List of scheduled scan tasks
    """
    result = query_db(
        """
        SELECT id, name, description, cron_expression, interval_seconds,
               next_run_at, last_run_at, last_run_status, enabled, priority,
               config
        FROM scheduled_tasks
        WHERE task_type = 'opportunity_scan'
        ORDER BY priority DESC, next_run_at ASC
        """
    )
    return result.get("rows", [])


# =============================================================================
# MARKET SCANNING LOGIC
# =============================================================================


def scan_servicetitan_opportunities(
    scan_id: str,
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Scan ServiceTitan for revenue opportunities.
    Looks for: stale leads, unbilled work, membership renewals, follow-ups.
    
    Args:
        scan_id: The scan record ID
        config: Scan configuration
        
    Returns:
        Dict with opportunities found
    """
    config = config or {}
    opportunities = []
    duplicates = 0
    
    # This would integrate with ServiceTitan API via JUGGERNAUT MCP
    # For now, define the scanning logic pattern
    
    scan_targets = config.get("targets", [
        "stale_estimates",      # Estimates > 7 days with no follow-up
        "membership_renewals",  # Memberships expiring in 30 days
        "unbilled_work",        # Completed jobs not invoiced
        "abandoned_calls",      # Calls that didn't convert
        "recall_candidates"     # Past customers for maintenance
    ])
    
    log_execution(
        worker_id="SCANNER",
        action="scan.servicetitan",
        message=f"Scanning ServiceTitan for: {', '.join(scan_targets)}",
        details={"scan_id": scan_id, "targets": scan_targets}
    )
    
    # Placeholder for actual ServiceTitan API integration
    # Each target would query the API and create opportunities
    
    return {
        "success": True,
        "scan_id": scan_id,
        "opportunities_found": len(opportunities),
        "duplicates_skipped": duplicates,
        "targets_scanned": scan_targets
    }


def scan_angi_leads(
    scan_id: str,
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Scan Angi for new leads that need follow-up.
    
    Args:
        scan_id: The scan record ID
        config: Scan configuration
        
    Returns:
        Dict with opportunities found
    """
    config = config or {}
    opportunities = []
    
    log_execution(
        worker_id="SCANNER",
        action="scan.angi",
        message="Scanning Angi leads",
        details={"scan_id": scan_id}
    )
    
    # Would integrate with Angi MCP tool
    # angi:angi_get_leads with status filters
    
    return {
        "success": True,
        "scan_id": scan_id,
        "opportunities_found": len(opportunities)
    }


def scan_market_trends(
    scan_id: str,
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Scan web for market opportunities and trends.
    
    Args:
        scan_id: The scan record ID
        config: Scan configuration
        
    Returns:
        Dict with opportunities found
    """
    config = config or {}
    search_terms = config.get("search_terms", [])
    
    log_execution(
        worker_id="SCANNER",
        action="scan.market",
        message=f"Scanning market for: {search_terms}",
        details={"scan_id": scan_id, "terms": search_terms}
    )
    
    # Would use web search tool to find opportunities
    
    return {
        "success": True,
        "scan_id": scan_id,
        "search_terms": search_terms
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Scan Management
    "start_scan",
    "complete_scan",
    "fail_scan",
    "get_scan_history",
    
    # Opportunity Identification
    "identify_opportunity",
    "identify_opportunity_with_dedup",
    
    # Scoring
    "score_opportunity",
    "bulk_score_opportunities",
    "get_top_opportunities",
    
    # Duplicate Detection
    "compute_opportunity_fingerprint",
    "check_duplicate",
    
    # Scheduling
    "schedule_scan",
    "get_scheduled_scans",
    
    # Market Scanning
    "scan_servicetitan_opportunities",
    "scan_angi_leads",
    "scan_market_trends",
]

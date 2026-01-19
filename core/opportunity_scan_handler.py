"""Opportunity Scan Handler - Handles scheduled opportunity scans.

This module provides the handler function for the opportunity_scan scheduled task type.
It orchestrates scanning of configured opportunity sources and creates evaluation tasks
for high-scoring opportunities.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4


def handle_opportunity_scan(task, execute_sql, log_action):
    """Handle an opportunity_scan scheduled task.
    
    Orchestrates the scanning of all active opportunity sources, generates
    opportunities, saves them to the database, and creates evaluation tasks
    for high-scoring opportunities.
    
    Args:
        task: The scheduled task dict containing config parameters.
        execute_sql: Function to execute SQL queries against the database.
        log_action: Function to log actions and events.
        
    Returns:
        dict: Results containing success status, scan_id (if successful),
              sources_scanned, opportunities_found, opportunities_qualified,
              and tasks_created counts. On failure, includes error message.
    """
    config = task.get("config", {})
    if isinstance(config, str):
        config = json.loads(config)
    min_score = config.get("min_confidence_score", 0.7)
    create_tasks = config.get("create_tasks_for_high_scoring", True)
    results = {"sources_scanned": 0, "opportunities_found": 0, "opportunities_qualified": 0, "tasks_created": 0}
    try:
        src = execute_sql("SELECT id, name, source_type FROM opportunity_sources WHERE active = true")
        sources = src.get("rows", [])
        if not sources:
            return {"success": True, **results}
        scan_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        cfg = json.dumps(config).replace("'", "''")
        execute_sql(f"INSERT INTO opportunity_scans (id, scan_type, source, scan_config, triggered_by, status, started_at) VALUES ('{scan_id}', 'scheduled', 'all', '{cfg}', 'engine', 'running', '{now}')")
        for source in sources:
            sid, sname, stype = source["id"], source["name"], source["source_type"]
            opps = _gen_opps(sid, stype)
            for opp in opps:
                oid = str(uuid4())
                conf = opp.get("confidence", 0.5)
                desc = opp["desc"].replace("'", "''")
                meta = json.dumps(opp.get("meta", {})).replace("'", "''")
                execute_sql(f"INSERT INTO opportunities (id, source_id, opportunity_type, category, estimated_value, confidence_score, status, stage, description, metadata, created_by) VALUES ('{oid}', '{sid}', '{opp['type']}', '{opp['cat']}', {opp.get('val', 0)}, {conf}, 'new', 'identified', '{desc}', '{meta}', 'engine')")
                results["opportunities_found"] += 1
                if conf >= min_score and create_tasks:
                    results["opportunities_qualified"] += 1
                    tid = str(uuid4())
                    title = f"Evaluate: {desc[:100]}"
                    pay = json.dumps({"opp_id": oid, "src": sname}).replace("'", "''")
                    execute_sql(f"INSERT INTO governance_tasks (id, task_type, title, description, priority, status, payload, created_by) VALUES ('{tid}', 'evaluation', '{title}', 'High-scoring opportunity', 'medium', 'pending', '{pay}', 'engine')")
                    results["tasks_created"] += 1
            results["sources_scanned"] += 1
        rs = json.dumps(results).replace("'", "''")
        execute_sql(f"UPDATE opportunity_scans SET status = 'completed', completed_at = NOW(), opportunities_found = {results['opportunities_found']}, opportunities_qualified = {results['opportunities_qualified']}, results_summary = '{rs}' WHERE id = '{scan_id}'")
        log_action("opportunity_scan.complete", f"Scan done: {results['opportunities_found']} found", "info")
        return {"success": True, "scan_id": scan_id, **results}
    except Exception as e:
        log_action("opportunity_scan.failed", str(e), "error")
        return {"success": False, "error": str(e), **results}


def _gen_opps(source_id, source_type):
    """Generate sample opportunities for a given source.
    
    This is a placeholder implementation that generates test opportunities.
    In production, this would call real APIs for each source type.
    
    Args:
        source_id: The UUID of the opportunity source.
        source_type: The type of source (e.g., 'expired_domains', 'trending_niches').
        
    Returns:
        list: List of opportunity dicts with type, cat, desc, val, confidence, and meta.
    """
    now = datetime.now(timezone.utc).isoformat()
    opps = []
    if source_type == "expired_domains":
        opps.append({"type": "digital_asset", "cat": "domain", "desc": "Expired domain with backlinks", "val": 500, "confidence": 0.65, "meta": {"src": source_type, "t": now}})
    elif source_type == "trending_niches":
        opps.append({"type": "market", "cat": "trend", "desc": "Rising search trend in target category", "val": 1000, "confidence": 0.75, "meta": {"src": source_type, "t": now}})
    elif source_type == "saas_ideas":
        opps.append({"type": "product", "cat": "saas", "desc": "Competitor gap in product space", "val": 5000, "confidence": 0.80, "meta": {"src": source_type, "t": now}})
    return opps

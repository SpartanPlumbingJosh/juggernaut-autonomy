"""Opportunity Scan Handler - Handles scheduled opportunity scans.

This module provides the handler function for the opportunity_scan scheduled task type.
It orchestrates scanning of configured opportunity sources and creates evaluation tasks
for high-scoring opportunities.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from core.task_templates import ProposedTask, pick_diverse_tasks


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
    dedupe_hours = config.get("dedupe_hours", 6)
    results = {
        "sources_scanned": 0,
        "opportunities_found": 0,
        "opportunities_qualified": 0,
        "tasks_created": 0,
        "tasks_skipped_duplicate": 0,
    }
    scan_id = None
    
    try:
        src = execute_sql("SELECT id, name, source_type FROM opportunity_sources WHERE active = true")
        sources = src.get("rows", [])
        if not sources:
            # No sources configured: fall back to diversified proactive work generation
            created = _create_diverse_tasks(execute_sql, log_action, config)
            results["tasks_created"] += created.get("tasks_created", 0)
            results["tasks_skipped_duplicate"] += created.get("tasks_skipped_duplicate", 0)
            results["tasks_skipped_quality"] = created.get("tasks_skipped_quality", 0)
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
                dedupe_key_raw = opp.get("meta", {}).get("dedupe_key")
                if not dedupe_key_raw:
                    # Stable key based on source + type + identifying metadata
                    ident = (
                        opp.get("meta", {}).get("domain")
                        or opp.get("meta", {}).get("keyword")
                        or opp.get("meta", {}).get("gap")
                        or opp.get("desc")
                        or "unknown"
                    )
                    dedupe_key_raw = f"oppscan:{stype}:{sid}:{str(ident).strip().lower()}"

                # Escape for SQL string usage
                dedupe_key_escaped = str(dedupe_key_raw).replace("'", "''")

                desc = opp["desc"].replace("'", "''")
                meta = json.dumps(opp.get("meta", {})).replace("'", "''")
                execute_sql(f"INSERT INTO opportunities (id, source_id, opportunity_type, category, estimated_value, confidence_score, status, stage, description, metadata, created_by) VALUES ('{oid}', '{sid}', '{opp['type']}', '{opp['cat']}', {opp.get('val', 0)}, {conf}, 'new', 'identified', '{desc}', '{meta}', 'engine')")
                results["opportunities_found"] += 1
                if conf >= min_score and create_tasks:
                    results["opportunities_qualified"] += 1
                    tid = str(uuid4())
                    title = f"Evaluate: {desc[:100]}"

                    # Deduplication: skip if a similar evaluation task exists recently
                    try:
                        existing = execute_sql(
                            f"""
                            SELECT id
                            FROM governance_tasks
                            WHERE task_type = 'evaluation'
                              AND payload->>'dedupe_key' = '{dedupe_key_escaped}'
                              AND created_at > NOW() - INTERVAL '{int(dedupe_hours)} hours'
                            LIMIT 1
                            """
                        )
                        if existing.get("rows"):
                            results["tasks_skipped_duplicate"] += 1
                            try:
                                log_action(
                                    "opportunity_scan.task_skipped_duplicate",
                                    f"Skipped duplicate evaluation task: {dedupe_key_raw}",
                                    "info",
                                )
                            except Exception:
                                pass
                            continue
                    except Exception as dedupe_err:
                        # Best-effort: do not block task creation if dedupe query fails
                        log_action("opportunity_scan.dedupe_failed", str(dedupe_err), "warning")

                    pay = json.dumps(
                        {
                            "opp_id": oid,
                            "src": sname,
                            "dedupe_key": dedupe_key_raw,
                        }
                    ).replace("'", "''")
                    execute_sql(f"INSERT INTO governance_tasks (id, task_type, title, description, priority, status, payload, created_by) VALUES ('{tid}', 'evaluation', '{title}', 'High-scoring opportunity', 'medium', 'pending', '{pay}', 'engine')")
                    results["tasks_created"] += 1
                    try:
                        log_action(
                            "opportunity_scan.task_created",
                            f"Created evaluation task: {dedupe_key_raw}",
                            "info",
                        )
                    except Exception:
                        pass
            results["sources_scanned"] += 1

        # After scanning, also ensure we generate diverse meaningful work (when allowed)
        if create_tasks:
            created = _create_diverse_tasks(execute_sql, log_action, config)
            results["tasks_created"] += created.get("tasks_created", 0)
            results["tasks_skipped_duplicate"] += created.get("tasks_skipped_duplicate", 0)
            results["tasks_skipped_quality"] = created.get("tasks_skipped_quality", 0)
        
        rs = json.dumps(results).replace("'", "''")
        execute_sql(f"UPDATE opportunity_scans SET status = 'completed', completed_at = NOW(), opportunities_found = {results['opportunities_found']}, opportunities_qualified = {results['opportunities_qualified']}, results_summary = '{rs}' WHERE id = '{scan_id}'")
        log_action(
            "opportunity_scan.complete",
            (
                f"Scan done: found={results['opportunities_found']} qualified={results['opportunities_qualified']} "
                f"tasks_created={results['tasks_created']} tasks_skipped_duplicate={results['tasks_skipped_duplicate']}"
            ),
            "info",
        )
        return {"success": True, "scan_id": scan_id, **results}
    
    except Exception as e:
        log_action("opportunity_scan.failed", str(e), "error")
        # Mark scan as failed if it was created
        if scan_id:
            try:
                error_msg = str(e).replace("'", "''")[:500]
                execute_sql(f"UPDATE opportunity_scans SET status = 'failed', completed_at = NOW(), error_message = '{error_msg}' WHERE id = '{scan_id}'")
            except Exception:
                pass  # Best effort to mark failed
        return {"success": False, "error": str(e), **results}


def _create_diverse_tasks(execute_sql, log_action, config):
    """Create diverse, meaningful proactive tasks (non-hallucinated)."""
    max_tasks = int((config or {}).get("max_diverse_tasks", 3) or 3)
    recent_limit = int((config or {}).get("dedupe_last_n", 50) or 50)
    dedupe_hours = int((config or {}).get("dedupe_hours", 24) or 24)

    tasks_created = 0
    tasks_skipped_duplicate = 0
    tasks_skipped_quality = 0

    try:
        candidates = pick_diverse_tasks(
            execute_sql=execute_sql,
            max_tasks=max_tasks,
            recent_limit=recent_limit,
            dedupe_hours=dedupe_hours,
        )
    except Exception as e:
        try:
            log_action("proactive.diverse_generation_failed", str(e), "warning")
        except Exception:
            pass
        return {
            "tasks_created": 0,
            "tasks_skipped_duplicate": 0,
            "tasks_skipped_quality": 0,
        }

    for cand in candidates:
        if not isinstance(cand, ProposedTask):
            continue

        # Quality gate: must include success_criteria and dedupe_key
        payload = cand.payload if isinstance(cand.payload, dict) else {}
        if not payload.get("dedupe_key") or not payload.get("success_criteria"):
            tasks_skipped_quality += 1
            continue

        # Hard cap: no more than 2 tasks of same title in last 24h
        title_escaped = str(cand.title).replace("'", "''")
        try:
            title_cnt = execute_sql(
                f"""
                SELECT COUNT(*)::int as c
                FROM governance_tasks
                WHERE title = '{title_escaped}'
                  AND created_at > NOW() - INTERVAL '24 hours'
                """
            )
            c = int((title_cnt.get("rows") or [{}])[0].get("c") or 0)
            if c >= 2:
                tasks_skipped_duplicate += 1
                try:
                    log_action(
                        "proactive.task_skipped_duplicate",
                        f"Skipped (title cap): {cand.title}",
                        "info",
                    )
                except Exception:
                    pass
                continue
        except Exception:
            pass

        tid = str(uuid4())
        pay = json.dumps(payload).replace("'", "''")
        desc = str(cand.description or "").replace("'", "''")
        priority = str(cand.priority or "medium")
        task_type = str(cand.task_type or "workflow")

        if task_type in ("health_check", "recovery", "alert"):
            payload["original_task_type"] = task_type
            task_type = "workflow"
            pay = json.dumps(payload).replace("'", "''")

        try:
            execute_sql(
                f"""
                INSERT INTO governance_tasks (id, task_type, title, description, priority, status, payload, created_by, assigned_worker)
                VALUES ('{tid}', '{task_type}', '{title_escaped}', '{desc}', '{priority}', 'pending', '{pay}', 'engine', NULL)
                """
            )
            tasks_created += 1
            try:
                log_action(
                    "proactive.task_created",
                    f"Created proactive task: {payload.get('dedupe_key')}",
                    "info",
                )
            except Exception:
                pass
        except Exception as e:
            tasks_skipped_quality += 1
            try:
                log_action("proactive.task_create_failed", str(e), "warning")
            except Exception:
                pass

    return {
        "tasks_created": tasks_created,
        "tasks_skipped_duplicate": tasks_skipped_duplicate,
        "tasks_skipped_quality": tasks_skipped_quality,
    }


def _gen_opps(source_id, source_type):
    """Generate opportunities for a given source.

    Note: Previously this function produced placeholder / synthetic opportunities
    which created repetitive evaluation tasks. That behavior was removed.
    If you later add real API integrations, this is where they should live.
    """
    _ = (source_id, source_type)
    return []

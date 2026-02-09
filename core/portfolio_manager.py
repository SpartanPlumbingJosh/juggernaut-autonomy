from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.idea_generator import IdeaGenerator
from core.idea_scorer import IdeaScorer
from core.experiment_runner import create_experiment_from_idea, link_experiment_to_idea
from dateutil.relativedelta import relativedelta

TARGET_CENTS = 1_200_000_000  # $12M target
DEADLINE_DATE = datetime(2031, 12, 31).date()


def generate_revenue_ideas(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    context: Optional[Dict[str, Any]] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    context = context or {}
    gen = IdeaGenerator()
    ideas = gen.generate_ideas(context)[: int(limit)]

    created = 0
    failures: List[Dict[str, Any]] = []
    for idea in ideas:
        title = str(idea.get("title") or "")
        if not title:
            continue

        dedupe_key = f"revenue_idea:{title.strip().lower()}"
        title_esc = title.replace("'", "''")
        desc_esc = str(idea.get("description") or "").replace("'", "''")
        hyp_esc = str(idea.get("hypothesis") or "").replace("'", "''")
        estimates_json = json.dumps(idea.get("estimates") or {}).replace("'", "''")

        research_sources_json = json.dumps(idea.get("research_sources") or []).replace("'", "''")
        timeliness_esc = str(idea.get("timeliness") or "").replace("'", "''")
        constraints_json = json.dumps(idea.get("constraints") or {}).replace("'", "''")
        tags_json = json.dumps(idea.get("tags") or []).replace("'", "''")
        evidence_type_esc = str(idea.get("evidence_type") or "").replace("'", "''")
        evidence_details_json = json.dumps(idea.get("evidence_details") or {}).replace("'", "''")
        reported_timeline_esc = str(idea.get("reported_timeline") or "").replace("'", "''")
        capabilities_required_json = json.dumps(idea.get("capabilities_required") or []).replace("'", "''")

        reported_revenue_val = idea.get("reported_revenue")
        try:
            reported_revenue_sql = "NULL" if reported_revenue_val is None else str(float(reported_revenue_val))
        except Exception:
            reported_revenue_sql = "NULL"

        try:
            existing = execute_sql(
                f"""
                SELECT id
                FROM revenue_ideas
                WHERE lower(title) = lower('{title_esc}')
                LIMIT 1
                """
            )
            if existing.get("rows"):
                continue
        except Exception:
            pass

        try:
            execute_sql(
                f"""
                INSERT INTO revenue_ideas (
                    id, title, description, hypothesis,
                    score, score_breakdown, status,
                    created_at, updated_at,
                    estimates,
                    research_sources, timeliness,
                    evidence_type, evidence_details,
                    reported_revenue, reported_timeline,
                    capabilities_required,
                    tags,
                    constraints
                ) VALUES (
                    gen_random_uuid(),
                    '{title_esc}',
                    '{desc_esc}',
                    '{hyp_esc}',
                    NULL,
                    NULL,
                    'pending',
                    NOW(),
                    NOW(),
                    '{estimates_json}'::jsonb,
                    '{research_sources_json}'::jsonb,
                    {f"'{timeliness_esc}'" if timeliness_esc else "NULL"},
                    {f"'{evidence_type_esc}'" if evidence_type_esc else "NULL"},
                    '{evidence_details_json}'::jsonb,
                    {reported_revenue_sql},
                    {f"'{reported_timeline_esc}'" if reported_timeline_esc else "NULL"},
                    '{capabilities_required_json}'::jsonb,
                    '{tags_json}'::jsonb,
                    '{constraints_json}'::jsonb
                )
                """
            )
            created += 1
        except Exception:
            continue

    try:
        log_action(
            "revenue.idea_generation",
            f"Generated {created} revenue ideas",
            level="info",
            output_data={"created": created, "attempted": len(ideas)},
        )
    except Exception:
        pass

    return {"success": True, "created": created, "attempted": len(ideas)}


def score_pending_ideas(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    limit: int = 20,
) -> Dict[str, Any]:
    try:
        res = execute_sql(
            f"""
            SELECT id, title, description, hypothesis, estimates
            FROM revenue_ideas
            WHERE status IN ('pending')
            ORDER BY created_at ASC
            LIMIT {int(limit)}
            """
        )
        rows = res.get("rows", []) or []
    except Exception as e:
        return {"success": False, "error": str(e)}

    scorer = IdeaScorer()
    scored = 0

    for r in rows:
        idea_id = str(r.get("id") or "")
        if not idea_id:
            continue

        idea = {
            "title": r.get("title"),
            "description": r.get("description"),
            "hypothesis": r.get("hypothesis"),
            "estimates": r.get("estimates") or {},
        }

        s = scorer.score_idea(idea)
        score = float(s.get("score") or 0.0)
        breakdown_json = json.dumps(s.get("breakdown") or {}).replace("'", "''")

        try:
            execute_sql(
                f"""
                UPDATE revenue_ideas
                SET score = {score},
                    score_breakdown = '{breakdown_json}'::jsonb,
                    status = 'scored',
                    updated_at = NOW()
                WHERE id = '{idea_id.replace("'", "''")}'
                """
            )
            scored += 1
        except Exception:
            continue

    try:
        log_action(
            "revenue.idea_scoring",
            f"Scored {scored} revenue ideas",
            level="info",
            output_data={"scored": scored, "considered": len(rows)},
        )
    except Exception:
        pass

    return {"success": True, "scored": scored, "considered": len(rows)}


def start_experiments_from_top_ideas(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    max_new: int = 1,
    min_score: float = 60.0,
    budget: float = 20.0,
) -> Dict[str, Any]:
    try:
        res = execute_sql(
            f"""
            SELECT id, title, description, hypothesis, estimates, score
            FROM revenue_ideas
            WHERE status = 'scored'
              AND COALESCE(score, 0) >= {float(min_score)}
            ORDER BY score DESC NULLS LAST, created_at ASC
            LIMIT {int(max_new * 3)}
            """
        )
        ideas = res.get("rows", []) or []
    except Exception as e:
        return {"success": False, "error": str(e)}

    created = 0
    failures: List[Dict[str, Any]] = []

    for idea in ideas:
        if created >= max_new:
            break

        idea_id = str(idea.get("id") or "")
        if not idea_id:
            continue

        try:
            existing = execute_sql(
                f"""
                SELECT id
                FROM experiments
                WHERE idea_id = '{idea_id.replace("'", "''")}'
                LIMIT 1
                """
            )
            if existing.get("rows"):
                continue
        except Exception:
            pass

        create_res = create_experiment_from_idea(
            execute_sql=execute_sql,
            log_action=log_action,
            idea=idea,
            budget=budget,
        )
        if not create_res.get("success"):
            failures.append({"idea_id": idea_id, "error": str(create_res.get("error") or "unknown")[:200]})
            continue

        exp_id = create_res.get("experiment_id")
        if not exp_id:
            failures.append({"idea_id": idea_id, "error": "missing experiment_id"})
            continue

        link_experiment_to_idea(execute_sql=execute_sql, experiment_id=str(exp_id), idea_id=idea_id)

        try:
            execute_sql(
                f"""
                UPDATE revenue_ideas
                SET status = 'experimenting',
                    updated_at = NOW()
                WHERE id = '{idea_id.replace("'", "''")}'
                """
            )
        except Exception:
            pass

        created += 1

    try:
        log_action(
            "portfolio.rebalanced",
            "Portfolio rebalance completed",
            level="info",
            output_data={"new_experiments": created, "candidates": len(ideas)},
        )
    except Exception:
        pass

    out = {"success": True, "new_experiments": created, "candidates": len(ideas)}
    if failures:
        out["failures"] = failures[:10]
        out["failed"] = len(failures)
    return out


def calculate_revenue_trajectory(
    execute_sql: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    """Calculate current revenue trajectory vs target and required growth rate."""
    try:
        # Get all-time revenue
        all_time_result = execute_sql(
            "SELECT SUM(amount_cents) as total FROM revenue_events WHERE event_type = 'revenue'"
        )
        current_cents = float(all_time_result.get("rows", [{}])[0].get("total", 0))
        
        # Get monthly revenue
        monthly_result = execute_sql("""
            SELECT 
                DATE_TRUNC('month', recorded_at) as month,
                SUM(amount_cents) as revenue
            FROM revenue_events
            WHERE event_type = 'revenue'
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """)
        monthly_data = monthly_result.get("rows", []) or []
        
        # Calculate time remaining
        today = datetime.now().date()
        months_remaining = (DEADLINE_DATE.year - today.year) * 12 + (DEADLINE_DATE.month - today.month)
        if months_remaining <= 0:
            return {"error": "Deadline has passed"}

        # Calculate required growth
        remaining_cents = TARGET_CENTS - current_cents
        if remaining_cents <= 0:
            return {"status": "target_achieved"}

        # Calculate required monthly growth rate
        current_monthly_cents = float(abs(monthly_data[0]["revenue"])) if monthly_data else 0
        required_growth_rate = math.pow(remaining_cents / current_monthly_cents, 1/months_remaining) - 1 if current_monthly_cents > 0 else float('inf')

        # Project trajectory
        projection = []
        projected_value = current_cents
        date = today
        for _ in range(months_remaining):
            projected_value += current_monthly_cents
            projection.append({
                "date": str(date),
                "projected_cents": projected_value,
                "target_cents": TARGET_CENTS * (1 - ((DEADLINE_DATE - date).days / (DEADLINE_DATE - today).days))
            })
            date += relativedelta(months=1)
            current_monthly_cents *= (1 + required_growth_rate)

        # Identify underperforming sources
        source_result = execute_sql("""
            SELECT source, SUM(amount_cents) as revenue, 
                   COUNT(*) as transactions
            FROM revenue_events
            WHERE event_type = 'revenue'
              AND recorded_at >= NOW() - INTERVAL '90 days'
            GROUP BY source
            ORDER BY revenue DESC
        """)
        sources = source_result.get("rows", [])
        underperforming = [s for s in sources if float(s["revenue"]) < (TARGET_CENTS / months_remaining / 10)]  # < 10% of monthly requirement
 
        return {
            "current_cents": current_cents,
            "target_cents": TARGET_CENTS,
            "months_remaining": months_remaining,
            "required_monthly_growth": required_growth_rate,
            "projection": projection,
            "monthly_trend": monthly_data,
            "underperforming_sources": underperforming,
            "status": "tracking"
        }
    except Exception as e:
        return {"error": str(e)}


def trigger_optimization_protocols(
    execute_sql: Callable[[str], Dict[str, Any]], 
    log_action: Callable[..., Any],
    underperforming_threshold: float = 0.1
) -> Dict[str, Any]:
    """Automatically initiate optimization experiments for underperforming streams."""
    trajectory = calculate_revenue_trajectory(execute_sql)
    if trajectory.get("error"):
        return {"success": False, "error": trajectory["error"]}

    if "underperforming_sources" not in trajectory:
        return {"success": False, "error": "No performance data available"}

    created = 0
    for source in trajectory["underperforming_sources"]:
        source_name = source["source"]
        context = {
            "optimize_source": source_name,
            "current_revenue": source["revenue"],
            "target_revenue": TARGET_CENTS / trajectory["months_remaining"],
            "performance_gap": (TARGET_CENTS / trajectory["months_remaining"]) - source["revenue"]
        }

        try:
            # Generate optimization ideas
            result = generate_revenue_ideas(
                execute_sql=execute_sql,
                log_action=log_action,
                context=context,
                limit=3
            )
            if result.get("created", 0) > 0:
                created += result["created"]
        except Exception as e:
            log_action("optimization.failed", f"Failed to generate ideas for {source_name}", error=str(e))

    return {
        "success": True,
        "optimization_experiments_created": created,
        "underperforming_sources_processed": len(trajectory["underperforming_sources"])
    }


def review_experiments_stub(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
) -> Dict[str, Any]:
    """Review running experiments and trigger learning loop for completed ones."""
    try:
        from core.learning_loop import on_experiment_complete
    except ImportError:
        on_experiment_complete = None
    
    try:
        res = execute_sql(
            """
            SELECT e.id, e.name, e.status, e.budget_spent, e.budget_limit, e.start_date, e.created_at,
                   COALESCE(
                       (SELECT SUM(net_amount) FROM revenue_events WHERE attribution->>'experiment_id' = e.id::text),
                       0
                   ) as revenue_generated,
                   COALESCE(e.budget_spent, 0) as actual_cost, e.experiment_type, e.metadata, e.hypothesis
            FROM experiments e
            WHERE e.status IN ('running', 'completed')
            ORDER BY e.updated_at DESC NULLS LAST, e.created_at DESC
            LIMIT 50
            """
        )
        rows = res.get("rows", []) or []
    except Exception as e:
        return {"success": False, "error": str(e)}

    running_count = 0
    completed_count = 0
    learning_triggered = 0
    
    for exp in rows:
        exp_id = exp.get("id")
        status = exp.get("status")
        
        if status == "running":
            running_count += 1
            
            budget_spent = float(exp.get("budget_spent") or 0)
            budget_limit = float(exp.get("budget_limit") or 0)
            
            if budget_limit > 0 and budget_spent >= budget_limit:
                try:
                    execute_sql(f"""
                        UPDATE experiments 
                        SET status = 'completed',
                            completed_at = NOW()
                        WHERE id = '{exp_id}'
                    """)
                    status = "completed"
                    log_action(
                        "experiment.auto_completed",
                        f"Experiment {exp.get('name')} completed (budget exhausted)",
                        level="info",
                        output_data={"experiment_id": exp_id, "budget_spent": budget_spent}
                    )
                except Exception as e:
                    log_action(
                        "experiment.completion_failed",
                        f"Failed to mark experiment complete: {str(e)}",
                        level="error",
                        error_data={"experiment_id": exp_id, "error": str(e)}
                    )
        
        if status == "completed" and on_experiment_complete:
            completed_count += 1
            
            revenue = float(exp.get("revenue_generated") or 0)
            cost = float(exp.get("actual_cost") or exp.get("budget_spent") or 0)
            roi = ((revenue - cost) / cost * 100) if cost > 0 else 0
            
            experiment_data = {
                "id": exp_id,
                "name": exp.get("name"),
                "status": status,
                "experiment_type": exp.get("experiment_type", "unknown"),
                "revenue_generated": revenue,
                "actual_cost": cost,
                "budget_spent": exp.get("budget_spent"),
                "roi": roi,
                "metadata": exp.get("metadata"),
                "hypothesis": exp.get("hypothesis")
            }
            
            try:
                check_sql = f"""
                    SELECT COUNT(*) as count 
                    FROM learnings 
                    WHERE source_task_id = '{exp_id}' 
                    AND category = 'experiment_outcome'
                """
                check_res = execute_sql(check_sql)
                already_processed = (check_res.get("rows", [{}])[0] or {}).get("count", 0) > 0
                
                if not already_processed:
                    on_experiment_complete(execute_sql, log_action, exp_id, experiment_data)
                    learning_triggered += 1
                    log_action(
                        "learning.triggered",
                        f"Learning loop triggered for experiment {exp.get('name')}",
                        level="info",
                        output_data={"experiment_id": exp_id, "roi": roi}
                    )
            except Exception as e:
                log_action(
                    "learning.trigger_failed",
                    f"Failed to trigger learning loop: {str(e)}",
                    level="error",
                    error_data={"experiment_id": exp_id, "error": str(e)}
                )

    try:
        log_action(
            "experiment.reviewed",
            f"Experiment review completed: {running_count} running, {completed_count} completed, {learning_triggered} learning triggered",
            level="info",
            output_data={
                "running": running_count,
                "completed": completed_count,
                "learning_triggered": learning_triggered
            },
        )
    except Exception:
        pass

    return {
        "success": True,
        "running": running_count,
        "completed": completed_count,
        "learning_triggered": learning_triggered
    }

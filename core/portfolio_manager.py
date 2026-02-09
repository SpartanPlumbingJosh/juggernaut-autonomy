from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from core.idea_generator import IdeaGenerator
from core.idea_scorer import IdeaScorer
from core.experiment_runner import create_experiment_from_idea, link_experiment_to_idea

@dataclass
class BillingCycle:
    user_id: str
    billing_date: datetime
    amount_cents: int
    status: str = "pending"  # pending, processed, failed
    
@dataclass
class UserAccount:
    user_id: str
    email: str
    created_at: datetime
    status: str = "active"  # active, suspended, canceled
    billing_plan: str = "basic"  # basic, pro, enterprise
    last_payment_date: Optional[datetime] = None
    
@dataclass
class ServiceDelivery:
    user_id: str
    service_id: str
    delivery_date: datetime
    status: str = "pending"  # pending, delivered, failed
    metadata: Optional[Dict] = None


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


def process_billing_cycle(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    billing_date: datetime = datetime.now(timezone.utc)
) -> Dict[str, Any]:
    """Process monthly billing for all active users."""
    try:
        # Get all active users
        users_res = execute_sql(
            f"""
            SELECT user_id, email, billing_plan 
            FROM users 
            WHERE status = 'active'
            """
        )
        users = users_res.get("rows", []) or []
        
        processed = 0
        failures = []
        
        for user in users:
            user_id = user.get("user_id")
            plan = user.get("billing_plan")
            
            # Get pricing based on plan
            pricing = {
                "basic": 9900,  # $99.00
                "pro": 19900,
                "enterprise": 49900
            }.get(plan, 0)
            
            if pricing <= 0:
                failures.append({"user_id": user_id, "error": "invalid_plan"})
                continue
            
            try:
                # Create billing record
                execute_sql(
                    f"""
                    INSERT INTO billing_cycles (
                        user_id, billing_date, amount_cents, status
                    ) VALUES (
                        '{user_id}',
                        '{billing_date.isoformat()}',
                        {pricing},
                        'pending'
                    )
                    """
                )
                
                # Attempt payment processing
                # TODO: Integrate with payment gateway
                payment_success = True  # Mock for now
                
                if payment_success:
                    execute_sql(
                        f"""
                        UPDATE billing_cycles
                        SET status = 'processed'
                        WHERE user_id = '{user_id}'
                          AND billing_date = '{billing_date.isoformat()}'
                        """
                    )
                    execute_sql(
                        f"""
                        UPDATE users
                        SET last_payment_date = NOW()
                        WHERE user_id = '{user_id}'
                        """
                    )
                    processed += 1
                else:
                    execute_sql(
                        f"""
                        UPDATE billing_cycles
                        SET status = 'failed'
                        WHERE user_id = '{user_id}'
                          AND billing_date = '{billing_date.isoformat()}'
                        """
                    )
                    failures.append({"user_id": user_id, "error": "payment_failed"})
                    
            except Exception as e:
                failures.append({"user_id": user_id, "error": str(e)})
                continue
                
        log_action(
            "billing.processed",
            f"Processed billing for {processed} users",
            level="info",
            output_data={
                "processed": processed,
                "failures": failures,
                "billing_date": billing_date.isoformat()
            }
        )
        
        return {
            "success": True,
            "processed": processed,
            "failures": failures
        }
        
    except Exception as e:
        log_action(
            "billing.failed",
            f"Billing processing failed: {str(e)}",
            level="error"
        )
        return {"success": False, "error": str(e)}

def deliver_services(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
) -> Dict[str, Any]:
    """Deliver pending services to users."""
    try:
        # Get pending services
        services_res = execute_sql(
            """
            SELECT user_id, service_id, metadata
            FROM service_deliveries
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 100
            """
        )
        services = services_res.get("rows", []) or []
        
        delivered = 0
        failures = []
        
        for service in services:
            user_id = service.get("user_id")
            service_id = service.get("service_id")
            
            try:
                # TODO: Actual service delivery logic
                delivery_success = True  # Mock for now
                
                if delivery_success:
                    execute_sql(
                        f"""
                        UPDATE service_deliveries
                        SET status = 'delivered',
                            delivered_at = NOW()
                        WHERE user_id = '{user_id}'
                          AND service_id = '{service_id}'
                        """
                    )
                    delivered += 1
                else:
                    execute_sql(
                        f"""
                        UPDATE service_deliveries
                        SET status = 'failed'
                        WHERE user_id = '{user_id}'
                          AND service_id = '{service_id}'
                        """
                    )
                    failures.append({"user_id": user_id, "service_id": service_id})
                    
            except Exception as e:
                failures.append({"user_id": user_id, "service_id": service_id, "error": str(e)})
                continue
                
        log_action(
            "services.delivered",
            f"Delivered {delivered} services",
            level="info",
            output_data={
                "delivered": delivered,
                "failures": failures
            }
        )
        
        return {
            "success": True,
            "delivered": delivered,
            "failures": failures
        }
        
    except Exception as e:
        log_action(
            "services.delivery_failed",
            f"Service delivery failed: {str(e)}",
            level="error"
        )
        return {"success": False, "error": str(e)}

def monitor_system_health(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
) -> Dict[str, Any]:
    """Monitor system health and performance."""
    try:
        # Get key metrics
        metrics_res = execute_sql(
            """
            SELECT 
                (SELECT COUNT(*) FROM users WHERE status = 'active') as active_users,
                (SELECT COUNT(*) FROM billing_cycles WHERE status = 'processed' AND billing_date >= NOW() - INTERVAL '1 month') as successful_payments,
                (SELECT COUNT(*) FROM service_deliveries WHERE status = 'delivered' AND delivered_at >= NOW() - INTERVAL '1 day') as daily_deliveries,
                (SELECT COUNT(*) FROM experiments WHERE status = 'running') as running_experiments
            """
        )
        metrics = metrics_res.get("rows", [{}])[0] or {}
        
        log_action(
            "system.health_check",
            "System health check completed",
            level="info",
            output_data=metrics
        )
        
        return {
            "success": True,
            "metrics": metrics
        }
        
    except Exception as e:
        log_action(
            "system.health_check_failed",
            f"System health check failed: {str(e)}",
            level="error"
        )
        return {"success": False, "error": str(e)}

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

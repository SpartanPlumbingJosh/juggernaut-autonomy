"""Experiment executor that creates and manages tasks for running experiments.

When an experiment is in 'running' status, this module:
1. Determines what type of experiment it is
2. Checks what tasks already exist for it
3. Creates the next phase of tasks if previous phase is complete
4. Updates experiment progress
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def _normalize_task_priority(value: Any) -> str:
    """Normalize legacy integer priorities to DB enum values."""

    # Valid DB enum values for governance_tasks.priority
    allowed = {"critical", "high", "normal", "low", "deferred"}

    if value is None:
        return "normal"

    if isinstance(value, str):
        v = value.strip().lower()
        if v in allowed:
            return v
        # Legacy value mapping
        if v == "medium":
            return "normal"
        if v.isdigit():
            try:
                value = int(v)
            except Exception:
                return "normal"
        else:
            return "normal"

    if isinstance(value, (int, float)):
        n = int(value)
        # Legacy convention: lower number == higher priority.
        if n <= 1:
            return "high"
        if n == 2:
            return "normal"
        if n == 3:
            return "normal"
        if n == 4:
            return "low"
        if n >= 5:
            return "deferred"

    return "normal"


# Task templates for each experiment type
EXPERIMENT_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "review_response_service": [
        {
            "phase": 1,
            "title": "Research: Find 50 local businesses needing review help",
            "task_type": "research",
            "description": """Find 50 local businesses that have unanswered Google reviews.

SEARCH METHOD:
1. Use Google search: "site:google.com/maps [city] [industry] reviews"
2. Look for businesses with visible 1-3 star reviews that have no owner response
3. Find their contact email (website, Facebook, or Google listing)

OUTPUT FORMAT (JSON array in completion_evidence):
[
  {
    "business_name": "Example Plumbing",
    "google_maps_url": "https://google.com/maps/place/...",
    "industry": "plumbing",
    "city": "Phoenix",
    "unanswered_review_count": 3,
    "example_review": "Terrible service, no one called back...",
    "contact_email": "info@example.com",
    "email_source": "website"
  }
]

Target: 50 businesses across various service industries (plumbing, HVAC, electrical, restaurants, salons, auto repair, dental, legal).""",
            "priority": 1
        },
        {
            "phase": 2,
            "title": "Outreach: Email first 10 businesses with review service pitch",
            "task_type": "outreach",
            "description": """Send personalized cold emails to the first 10 businesses from Phase 1 research.

EMAIL TEMPLATE:
---
Subject: I noticed [Business Name] has some unanswered reviews

Hi,

I was looking at [Business Name]'s Google reviews and noticed a few that haven't been responded to yet - including one from [approximate date] mentioning [brief issue from their actual review].

Quick, thoughtful responses to reviews (even negative ones) can turn unhappy customers into loyal ones, and show future customers you care.

I help local businesses manage their review responses for $49/month. I draft professional, on-brand responses within 24 hours of any new review.

Want me to write responses to your 3 most recent unanswered reviews for free? Just reply "yes" and I'll send them over today.

Best,
JUGGERNAUT Automation
---

PERSONALIZATION REQUIRED:
- Use actual business name
- Reference a real unanswered review you found
- Make it specific to their industry

TRACKING (record in completion_evidence):
{
  "emails_sent": 10,
  "businesses_contacted": ["Business 1", "Business 2", ...],
  "send_timestamps": ["2026-01-31T10:00:00Z", ...]
}""",
            "priority": 1,
            "depends_on_phase": 1
        },
        {
            "phase": 3,
            "title": "Fulfill: Deliver free sample responses to interested prospects",
            "task_type": "fulfillment",
            "description": """For anyone who replied positively to Phase 2 outreach emails:

STEPS:
1. Find their 3 most recent unanswered Google reviews
2. Write professional, empathetic responses for each review
3. Email the drafted responses to them
4. Include clear CTA for paid service

RESPONSE GUIDELINES:
- Acknowledge the customer's concern
- Apologize if appropriate (without admitting fault)
- Offer to make it right / invite them back
- Keep it professional but warm
- 2-4 sentences max

EMAIL TEMPLATE FOR SAMPLES:
---
Subject: Your free review responses are ready

Hi [Owner Name],

Here are draft responses for your 3 most recent unanswered reviews. Feel free to copy these directly into Google or tweak them to match your voice.

REVIEW 1: [Star rating] stars from [Reviewer name]
Original: "[Review text]"

SUGGESTED RESPONSE:
"[Your drafted response]"

---

REVIEW 2: [Star rating] stars from [Reviewer name]
Original: "[Review text]"

SUGGESTED RESPONSE:
"[Your drafted response]"

---

REVIEW 3: [Star rating] stars from [Reviewer name]
Original: "[Review text]"

SUGGESTED RESPONSE:
"[Your drafted response]"

---

If you'd like me to handle all your review responses going forward, it's $49/month and I respond within 24 hours. Just reply "start" to begin.

Best,
JUGGERNAUT Automation
---

TRACKING (record in completion_evidence):
{
  "replies_received": 3,
  "samples_sent": 2,
  "conversions_to_paid": 1,
  "revenue_generated": 49.00
}""",
            "priority": 1,
            "depends_on_phase": 2
        }
    ]
}


def classify_experiment(experiment: Dict[str, Any]) -> Optional[str]:
    """Determine experiment type from its name/description."""
    name = (experiment.get("name") or "").lower()
    desc = (experiment.get("description") or "").lower()
    combined = f"{name} {desc}"
    
    # Check for explicit experiment_type field first (preferred method)
    exp_type = experiment.get("experiment_type")
    if exp_type and isinstance(exp_type, str):
        return exp_type.lower()
    
    # Pattern matching on experiment name/description
    # Order matters here - more specific patterns first
    
    # Match domain flip experiments (highest priority)
    if "domain flip" in combined or "domain-flip" in combined or "domain_flip" in combined:
        return "domain_flip"
    
    # Match specific experiment prefixes
    if "revenue-exp" in combined and "domain flip" in combined:
        return "domain_flip"
        
    if "review" in combined and ("response" in combined or "service" in combined):
        return "review_response_service"
        
    # Match rollback capability tests
    if "rollback" in combined and "test" in combined:
        return "rollback_test"
        
    # Match FIX-XX pattern for rollback tests
    if combined.startswith("fix-") or combined.startswith("fix:") or "fix-" in combined:
        return "rollback_test"
        
    # Match wire-up tests
    if "wire" in combined and "test" in combined:
        return "test"
        
    # Match revenue experiments
    if "revenue" in combined and "exp" in combined:
        return "revenue"
    
    # Default to "revenue" for unknown experiments
    return "revenue"


def get_existing_tasks(
    experiment_id: str,
    execute_sql: Callable[[str], Dict[str, Any]]
) -> Dict[str, Any]:
    """Get tasks already created for this experiment."""

    # Search for tasks linked to this experiment
    exp_id_short = experiment_id[:8] if experiment_id else ""
    
    result = execute_sql(f"""
        SELECT id, title, status, task_type, priority,
               payload::text as payload_text,
               completion_evidence,
               created_at
        FROM governance_tasks
        WHERE (payload::text LIKE '%{experiment_id}%'
               OR tags::text LIKE '%{exp_id_short}%')
          AND payload::text LIKE '%"auto_generated": true%'
        ORDER BY created_at ASC
    """)

    tasks = result.get("rows", []) or []

    by_status: Dict[str, List[Dict[str, Any]]] = {
        "pending": [], 
        "in_progress": [], 
        "completed": [], 
        "failed": []
    }
    
    for t in tasks:
        status = t.get("status", "pending")
        if status in by_status:
            by_status[status].append(t)
        else:
            by_status["pending"].append(t)

    return {
        "total": len(tasks),
        "by_status": by_status,
        "all_tasks": tasks
    }


def create_task_for_experiment(
    experiment: Dict[str, Any],
    template: Dict[str, Any],
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any]
) -> Optional[str]:
    """Create a single task from a template for an experiment."""

    task_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    exp_id = experiment.get("id", "")
    exp_name = (experiment.get("name") or "Unknown").replace("'", "''")

    title = (template.get("title") or "Experiment Task").replace("'", "''")
    task_type = template.get("task_type", "research")
    description = (template.get("description") or "").replace("'", "''")
    priority = _normalize_task_priority(template.get("priority"))
    phase = template.get("phase", 1)

    # Build payload with experiment reference
    payload = {
        "experiment_id": exp_id,
        "experiment_name": experiment.get("name", "Unknown"),
        "phase": phase,
        "auto_generated": True,
        "template_title": template.get("title", "")
    }
    payload_json = json.dumps(payload).replace("'", "''")

    # Build tags for easy lookup
    exp_id_short = exp_id[:8] if exp_id else "unknown"
    tags = ["experiment", f"exp-{exp_id_short}", f"phase-{phase}", "auto-generated"]
    tags_json = json.dumps(tags).replace("'", "''")

    try:
        execute_sql(f"""
            INSERT INTO governance_tasks (
                id, title, description, task_type, status, priority,
                payload, tags, created_at, updated_at
            ) VALUES (
                '{task_id}',
                '{title}',
                '{description}',
                '{task_type}',
                'pending',
                '{priority}'::priority_level,
                '{payload_json}'::jsonb,
                '{tags_json}'::jsonb,
                '{now}',
                '{now}'
            )
        """)

        log_action(
            "experiment.task_created",
            f"Created Phase {phase} task for experiment: {template.get('title', 'Unknown')[:50]}",
            level="info",
            output_data={
                "task_id": task_id,
                "experiment_id": exp_id,
                "experiment_name": experiment.get("name"),
                "phase": phase,
                "task_type": task_type
            }
        )

        return task_id

    except Exception as e:
        logger.error(f"Failed to create experiment task: {e}")
        try:
            log_action(
                "experiment.task_creation_failed",
                f"Failed to create task: {str(e)[:100]}",
                level="error",
                output_data={"experiment_id": exp_id, "error": str(e)}
            )
        except Exception:
            pass
        return None


def get_phase_from_task(task: Dict[str, Any]) -> int:
    """Extract phase number from a task."""
    try:
        payload_text = task.get("payload_text", "{}")
        if isinstance(payload_text, str):
            payload = json.loads(payload_text)
        else:
            payload = payload_text or {}
        return int(payload.get("phase", 0))
    except Exception:
        return 0


def progress_single_experiment(
    experiment: Dict[str, Any],
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any]
) -> Dict[str, Any]:
    """Progress a single experiment by creating needed tasks."""

    exp_id = experiment.get("id", "")
    exp_name = experiment.get("name", "Unknown")

    # Classify the experiment type
    exp_type = classify_experiment(experiment)
    if not exp_type:
        log_action(
            "experiment.unknown_type",
            f"Cannot progress experiment - unknown type: {exp_name[:50]}",
            level="warn",
            output_data={"experiment_id": exp_id, "name": exp_name}
        )
        return {
            "experiment_id": exp_id,
            "experiment_name": exp_name,
            "status": "skipped",
            "reason": "Unknown experiment type - no templates available"
        }

    # Get templates for this experiment type
    templates = EXPERIMENT_TEMPLATES.get(exp_type, [])
    if not templates:
        return {
            "experiment_id": exp_id,
            "experiment_name": exp_name,
            "status": "skipped",
            "reason": f"No templates defined for experiment type: {exp_type}"
        }

    # Check what tasks already exist
    existing = get_existing_tasks(exp_id, execute_sql)

    # If no tasks exist yet, create Phase 1 tasks
    if existing["total"] == 0:
        phase_1_templates = [t for t in templates if t.get("phase", 1) == 1]
        created_ids = []
        
        for tmpl in phase_1_templates:
            task_id = create_task_for_experiment(experiment, tmpl, execute_sql, log_action)
            if task_id:
                created_ids.append(task_id)

        return {
            "experiment_id": exp_id,
            "experiment_name": exp_name,
            "status": "phase_started",
            "phase": 1,
            "tasks_created": len(created_ids),
            "task_ids": created_ids
        }

    # Check status of existing tasks
    pending = existing["by_status"].get("pending", [])
    in_progress = existing["by_status"].get("in_progress", [])
    completed = existing["by_status"].get("completed", [])
    failed = existing["by_status"].get("failed", [])

    # If there are still pending or in-progress tasks, wait for them
    if pending or in_progress:
        return {
            "experiment_id": exp_id,
            "experiment_name": exp_name,
            "status": "waiting_for_tasks",
            "pending_count": len(pending),
            "in_progress_count": len(in_progress),
            "completed_count": len(completed)
        }

    # If all tasks failed, report the problem
    if failed and not completed:
        return {
            "experiment_id": exp_id,
            "experiment_name": exp_name,
            "status": "blocked",
            "reason": "All tasks failed",
            "failed_count": len(failed)
        }

    # Find the maximum phase that's been completed
    max_completed_phase = 0
    for task in completed:
        phase = get_phase_from_task(task)
        if phase > max_completed_phase:
            max_completed_phase = phase

    # Determine next phase
    next_phase = max_completed_phase + 1
    next_phase_templates = [t for t in templates if t.get("phase") == next_phase]

    # If no more phases, experiment is complete
    if not next_phase_templates:
        log_action(
            "experiment.all_phases_complete",
            f"All phases complete for experiment: {exp_name[:50]}",
            level="info",
            output_data={
                "experiment_id": exp_id,
                "phases_completed": max_completed_phase,
                "total_tasks_completed": len(completed)
            }
        )
        return {
            "experiment_id": exp_id,
            "experiment_name": exp_name,
            "status": "all_phases_complete",
            "phases_completed": max_completed_phase,
            "total_tasks": len(completed)
        }

    # Create tasks for the next phase
    created_ids = []
    for tmpl in next_phase_templates:
        task_id = create_task_for_experiment(experiment, tmpl, execute_sql, log_action)
        if task_id:
            created_ids.append(task_id)

    return {
        "experiment_id": exp_id,
        "experiment_name": exp_name,
        "status": "phase_started",
        "phase": next_phase,
        "tasks_created": len(created_ids),
        "task_ids": created_ids,
        "previous_phase_completed": max_completed_phase
    }


def progress_experiments(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
) -> Dict[str, Any]:
    """Main entry point - progress all running experiments.
    
    This function is called periodically by the engine to:
    1. Find all experiments in 'running' status
    2. Create tasks for experiments that need them
    3. Advance to next phase when current phase tasks complete
    """

    try:
        res = execute_sql("""
            SELECT id, name, description, status, hypothesis,
                   current_iteration, budget_spent, budget_limit
            FROM experiments
            WHERE status = 'running'
            ORDER BY created_at ASC
            LIMIT 10
        """)
        experiments = res.get("rows", []) or []
    except Exception as e:
        logger.error(f"Failed to fetch running experiments: {e}")
        return {"success": False, "error": str(e)}

    if not experiments:
        log_action(
            "experiment.none_running",
            "No running experiments to progress",
            level="info",
            output_data={"checked_at": datetime.now(timezone.utc).isoformat()}
        )
        return {
            "success": True,
            "running_experiments": 0,
            "experiments_progressed": 0,
            "tasks_created": 0
        }

    # Progress each experiment
    results = []
    total_tasks_created = 0
    
    for exp in experiments:
        try:
            result = progress_single_experiment(exp, execute_sql, log_action)
            results.append(result)
            total_tasks_created += result.get("tasks_created", 0)
        except Exception as e:
            logger.error(f"Error progressing experiment {exp.get('id')}: {e}")
            results.append({
                "experiment_id": exp.get("id"),
                "experiment_name": exp.get("name"),
                "status": "error",
                "error": str(e)
            })

    # Count how many experiments we actually progressed
    progressed_count = len([r for r in results if r.get("tasks_created", 0) > 0])

    log_action(
        "experiment.progress_cycle_complete",
        f"Checked {len(experiments)} experiments, created {total_tasks_created} tasks",
        level="info",
        output_data={
            "experiments_checked": len(experiments),
            "experiments_progressed": progressed_count,
            "total_tasks_created": total_tasks_created,
            "results_summary": [
                {"id": r.get("experiment_id", "")[:8], "status": r.get("status"), "tasks": r.get("tasks_created", 0)}
                for r in results
            ]
        }
    )

    return {
        "success": True,
        "running_experiments": len(experiments),
        "experiments_progressed": progressed_count,
        "total_tasks_created": total_tasks_created,
        "details": results
    }

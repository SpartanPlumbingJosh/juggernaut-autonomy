import json
from uuid import uuid4

from core.database import query_db, escape_sql_value

GOAL_WEEK1_100 = "65822ac4-2e02-4efc-8f75-50f1d36f1660"
EXPERIMENT_ID = "3fa0ca36-b84b-462e-9905-7951c53375ab"


def j(v):
    return escape_sql_value(json.dumps(v, ensure_ascii=False))


def s(v: str):
    return escape_sql_value(v)


def main() -> None:
    # Confirm enum labels for priority
    enum_sql = """
    SELECT e.enumlabel AS priority
    FROM pg_type t
    JOIN pg_enum e ON t.oid = e.enumtypid
    WHERE t.typname = 'task_priority'
    ORDER BY e.enumsortorder;
    """.strip()

    priority_enum = query_db(enum_sql)

    tasks = [
        {
            "title": "REVENUE-EXP-01: Domain Flip Pilot — Define niche filters + selection rubric",
            "task_type": "analysis",
            "priority": "critical",
            "description": "Define profitable niches + hard filters for undervalued domains. Produce an explicit rubric that can be used to score candidates under $20 (or reg-fee) and target resale >= $50 within 30 days.",
            "payload": {
                "experiment_id": EXPERIMENT_ID,
                "goal": "first_100_revenue",
                "constraints": {"max_cost_usd": 20, "min_sale_usd": 50, "time_horizon_days": 30},
                "deliverables": [
                    "niche shortlist (5-10)",
                    "keyword patterns",
                    "score rubric (age, length, keyword intent, brandability, comps)",
                ],
            },
            "requires_approval": False,
        },
        {
            "title": "REVENUE-EXP-01: Find 20 undervalued domain candidates (<= $20)",
            "task_type": "research",
            "priority": "critical",
            "description": "Find at least 20 candidate domains in profitable niches (HVAC, plumbing, home services, SaaS) with acquisition cost <= $20 (registration or closeout). Provide a table with price, registrar/market, and rationale.",
            "payload": {
                "experiment_id": EXPERIMENT_ID,
                "max_price_usd": 20,
                "count": 20,
                "niches": ["hvac", "plumbing", "home services", "local lead gen", "saas"],
                "deliverable_format": "table",
            },
            "requires_approval": False,
        },
        {
            "title": "REVENUE-EXP-01: Evaluate top 5 domain candidates (age/backlinks/keywords/comps)",
            "task_type": "analysis",
            "priority": "high",
            "description": "From the candidate list, pick top 5 and evaluate value: age, backlink profile (if any), keyword intent, comparable sales, brandability, and expected resale price. Recommend 1 best domain to acquire.",
            "payload": {
                "experiment_id": EXPERIMENT_ID,
                "top_n": 5,
                "deliverables": ["top 5 scored", "comps", "recommended acquisition"],
            },
            "requires_approval": False,
        },
        {
            "title": "REVENUE-EXP-01: Select best domain + finalize purchase plan (approval required)",
            "task_type": "workflow",
            "priority": "critical",
            "description": "Finalize the single best domain to buy. Provide exact checkout steps and confirm total cost <= $20. This task must pause for Josh approval before any spend.",
            "payload": {
                "experiment_id": EXPERIMENT_ID,
                "requires_spend": True,
                "max_spend_usd": 20,
                "approval_prompt": "Approve spending up to $20 to acquire the selected domain for REVENUE-EXP-01.",
            },
            "requires_approval": True,
            "approval_reason": "Spend authorization required: up to $20 to acquire domain",
        },
        {
            "title": "REVENUE-EXP-01: Create listing assets + list domain on marketplaces",
            "task_type": "workflow",
            "priority": "high",
            "description": "After acquisition, create listing copy, pricing (Buy Now >= $50), and list on Afternic, Dan, Sedo (and any other relevant marketplaces). Capture evidence: URLs/screenshots/IDs.",
            "payload": {
                "experiment_id": EXPERIMENT_ID,
                "marketplaces": ["afternic", "dan", "sedo"],
                "min_buy_now_usd": 50,
                "deliverables": ["listing copy", "prices", "listing links/evidence"],
            },
            "requires_approval": False,
        },
        {
            "title": "REVENUE-EXP-01: Monitor inquiries + weekly status report",
            "task_type": "analysis",
            "priority": "medium",
            "description": "Monitor the listing(s) for inquiries/offers. Produce a weekly status report with views/offers/messages and next actions. Continue until sold or 30 days elapsed.",
            "payload": {
                "experiment_id": EXPERIMENT_ID,
                "cadence": "weekly",
                "time_horizon_days": 30,
                "metrics": ["views", "offers", "messages", "sale"],
            },
            "requires_approval": False,
        },
    ]

    inserted_ids = []
    insert_errors = []

    for t in tasks:
        task_id = str(uuid4())
        inserted_ids.append(task_id)

        tags = ["mission", "revenue", "domain_flip", "REVENUE-EXP-01", "week1_100"]
        metadata = {"experiment_id": EXPERIMENT_ID, "mission": "juggernaut", "seeded_by": "db_seed_domain_flip.py"}

        requires_approval = bool(t.get("requires_approval"))
        approval_reason = t.get("approval_reason")

        sql = f"""
        INSERT INTO governance_tasks (
            id,
            goal_id,
            task_type,
            title,
            description,
            payload,
            priority,
            status,
            requires_approval,
            approval_reason,
            tags,
            metadata,
            created_by,
            created_at,
            updated_at,
            max_attempts,
            attempt_count,
            dry_run
        ) VALUES (
            {s(task_id)},
            {s(GOAL_WEEK1_100)},
            {s(t['task_type'])},
            {s(t['title'])},
            {s(t.get('description',''))},
            {j(t.get('payload', {}))}::jsonb,
            {s(t['priority'])}::task_priority,
            'pending',
            {'TRUE' if requires_approval else 'FALSE'},
            {s(approval_reason) if approval_reason else 'NULL'},
            {j(tags)}::jsonb,
            {j(metadata)}::jsonb,
            'JUGGERNAUT',
            NOW(),
            NOW(),
            3,
            0,
            FALSE
        );
        """.strip()

        try:
            query_db(sql)
        except Exception as e:
            insert_errors.append({"id": task_id, "title": t.get("title"), "error": str(e)})

    pending = query_db(
        """
        SELECT id, title, status, task_type, priority, requires_approval, created_at
        FROM governance_tasks
        WHERE status = 'pending'
        ORDER BY created_at DESC
        LIMIT 50;
        """.strip()
    )

    with open("seed_domain_flip_results.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "priority_enum": priority_enum,
                "inserted_ids": inserted_ids,
                "insert_errors": insert_errors,
                "pending": pending,
            },
            f,
            indent=2,
            default=str,
        )


if __name__ == "__main__":
    main()

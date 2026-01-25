import json

from core.database import query_db


def dump(name: str, result) -> None:
    with open(name, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)


def safe_query(sql: str):
    try:
        return {"ok": True, "result": query_db(sql)}
    except Exception as e:
        return {"ok": False, "error": str(e), "sql": sql}


def main() -> None:
    dump(
        "inspect_goals.json",
        safe_query(
            """
            SELECT id, title, description, status, target_value, target_unit, deadline, created_at
            FROM goals
            ORDER BY created_at DESC
            LIMIT 20;
            """.strip()
        ),
    )

    dump(
        "inspect_experiments.json",
        safe_query(
            """
            SELECT id, name, status, approved_at, created_at, updated_at
            FROM experiments
            ORDER BY COALESCE(approved_at, created_at) DESC
            LIMIT 50;
            """.strip()
        ),
    )

    dump(
        "inspect_domain_flip_candidates.json",
        safe_query(
            """
            SELECT id, name, status, approved_at, created_at, updated_at
            FROM experiments
            WHERE LOWER(name) LIKE '%domain%'
               OR LOWER(name) LIKE '%flip%'
               OR LOWER(name) LIKE '%domain flip%'
            ORDER BY COALESCE(approved_at, created_at) DESC
            LIMIT 50;
            """.strip()
        ),
    )

    dump(
        "inspect_governance_tasks_columns.json",
        safe_query(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'governance_tasks'
            ORDER BY ordinal_position;
            """.strip()
        ),
    )

    dump(
        "inspect_recent_tasks.json",
        safe_query(
            """
            SELECT id, title, status, task_type, priority, created_at, updated_at, completed_at
            FROM governance_tasks
            ORDER BY created_at DESC
            LIMIT 50;
            """.strip()
        ),
    )


if __name__ == "__main__":
    main()

import json

from core.database import query_db

TASK_ID = "cc40b40d-be5a-41c8-b84a-233159fb94c3"


def main() -> None:
    r = query_db(
        f"""
        SELECT id, goal_id, root_task_id, parent_task_id,
               title, task_type, status, priority,
               requires_approval, approval_reason,
               assigned_worker, assigned_at, started_at, completed_at, updated_at,
               attempt_count, max_attempts, next_retry_at,
               tags, metadata,
               error_message,
               LEFT(COALESCE(completion_evidence,''), 800) AS completion_evidence,
               result
        FROM governance_tasks
        WHERE id = '{TASK_ID}'::uuid;
        """.strip()
    )

    with open("debug_task_row.json", "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, default=str)


if __name__ == "__main__":
    main()

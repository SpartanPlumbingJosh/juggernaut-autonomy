import json

from core.database import query_db


def main() -> None:
    completed_inprogress_failed = query_db(
        """
        SELECT id, title, status, task_type, completed_at
        FROM governance_tasks
        WHERE status IN ('completed', 'in_progress', 'failed')
        ORDER BY completed_at DESC NULLS LAST
        LIMIT 10;
        """.strip()
    )

    waiting_approval = query_db(
        """
        SELECT id, title, status, task_type, updated_at
        FROM governance_tasks
        WHERE status = 'waiting_approval'
        ORDER BY updated_at DESC
        LIMIT 10;
        """.strip()
    )

    with open("task_status_check.json", "w", encoding="utf-8") as f:
        json.dump(completed_inprogress_failed, f, indent=2, default=str)

    with open("task_waiting_approval_check.json", "w", encoding="utf-8") as f:
        json.dump(waiting_approval, f, indent=2, default=str)


if __name__ == "__main__":
    main()

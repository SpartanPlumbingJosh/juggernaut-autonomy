import json

from core.database import query_db

TASK_IDS = [
    "cc40b40d-be5a-41c8-b84a-233159fb94c3",
    "8b51fc1a-c4cb-440c-839a-f7ed9609dd7b",
    "2ca8b324-3adc-4938-a5f7-fe920743ae2f",
    "cff581e4-a380-4f9f-a938-a7f50a3d9b2a",
    "f7d07bac-8337-4ab6-85e1-b1c3e9cd5bce",
    "2ba17d57-bcd6-4c07-95d9-af0ba008b6c4",
]


def dump(name: str, result) -> None:
    with open(name, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)


def main() -> None:
    ids = ",".join([f"'{i}'" for i in TASK_IDS])

    tasks = query_db(
        f"""
        SELECT id, title, status, task_type, priority, requires_approval,
               attempt_count, max_attempts,
               created_at, assigned_at, started_at, completed_at, updated_at,
               LEFT(COALESCE(completion_evidence,''), 240) AS completion_evidence_preview,
               error_message
        FROM governance_tasks
        WHERE id IN ({ids})
        ORDER BY created_at ASC;
        """.strip()
    )

    pending = query_db(
        """
        SELECT id, title, status, task_type, priority, requires_approval, created_at
        FROM governance_tasks
        WHERE status IN ('pending','in_progress','waiting_approval','failed')
          AND (tags ? 'domain_flip' OR tags ? 'REVENUE-EXP-01' OR (metadata->>'experiment_id') IS NOT NULL)
        ORDER BY created_at DESC
        LIMIT 50;
        """.strip()
    )

    dump("domain_flip_task_status.json", {"tasks": tasks, "active_related": pending})


if __name__ == "__main__":
    main()

import json

from core.database import query_db


def dump(name: str, result) -> None:
    with open(name, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)


def main() -> None:
    dump(
        "inspect_goals_columns.json",
        query_db(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='goals'
            ORDER BY ordinal_position;
            """.strip()
        ),
    )

    dump(
        "inspect_goals_rows.json",
        query_db(
            """
            SELECT *
            FROM goals
            ORDER BY created_at DESC
            LIMIT 50;
            """.strip()
        ),
    )


if __name__ == "__main__":
    main()

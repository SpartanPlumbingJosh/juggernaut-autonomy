-- Register critical monitoring and error scanning as scheduled tasks
-- These were built but never registered in the database

-- Critical monitoring - runs every 5 minutes
INSERT INTO scheduled_tasks (id, name, task_type, cron_expression, config, enabled, next_run_at, interval_seconds)
VALUES (
    gen_random_uuid(),
    'critical_monitoring',
    'critical_monitoring',
    '*/5 * * * *',
    '{}'::jsonb,
    TRUE,
    NOW(),
    300
)
ON CONFLICT (name) DO UPDATE SET
    task_type = EXCLUDED.task_type,
    cron_expression = EXCLUDED.cron_expression,
    enabled = TRUE,
    interval_seconds = 300;

-- Error scanning - runs every 15 minutes
INSERT INTO scheduled_tasks (id, name, task_type, cron_expression, config, enabled, next_run_at, interval_seconds)
VALUES (
    gen_random_uuid(),
    'error_scanning',
    'error_scanning',
    '*/15 * * * *',
    '{}'::jsonb,
    TRUE,
    NOW(),
    900
)
ON CONFLICT (name) DO UPDATE SET
    task_type = EXCLUDED.task_type,
    cron_expression = EXCLUDED.cron_expression,
    enabled = TRUE,
    interval_seconds = 900;

-- Stale task reset - runs every 10 minutes
INSERT INTO scheduled_tasks (id, name, task_type, cron_expression, config, enabled, next_run_at, interval_seconds)
VALUES (
    gen_random_uuid(),
    'stale_task_reset',
    'stale_task_reset',
    '*/10 * * * *',
    '{}'::jsonb,
    TRUE,
    NOW(),
    600
)
ON CONFLICT (name) DO UPDATE SET
    task_type = EXCLUDED.task_type,
    cron_expression = EXCLUDED.cron_expression,
    enabled = TRUE,
    interval_seconds = 600;

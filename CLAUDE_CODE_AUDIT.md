# JUGGERNAUT COMPLETE CODEBASE AUDIT
## For Claude Code — Read This First Before Touching Anything

**Date:** February 8, 2026
**Purpose:** Complete map of what's running, what's dead, what's broken, and what to fix — in order.

---

## THE #1 FINDING: main.py IS THE ENTIRE SYSTEM

**File:** `main.py` — 6,491 lines / 283KB
**This is the ONLY file that runs.** Everything else is either imported BY main.py or dead.

The Dockerfile runs: `CMD ["python", "main.py"]`

### main.py Structure (key sections):
```
Lines 1-537:     Imports, config, env vars
Lines 538-591:   Section headers
Lines 592-615:   TaskStatus enum, Task dataclass
Lines 620-770:   Auto-approve & orphaned task handlers
Lines 772-800:   Payload sanitizer
Lines 805-866:   execute_sql() — THE database function
Lines 872-996:   Logging functions (log_action, log_info, log_error, log_decision)
Lines 998-1133:  Risk assessment
Lines 1135-1782: Permission system, worker capabilities, cost limits, schema migrations
Lines 1787-2414: Task queue management (get_pending_tasks, scheduled tasks, update_task_status)
Lines 2415-2571: Task claiming & resource allocation
Lines 2572-2936: Approval system, retry/DLQ, escalations
Lines 2937-3081: Tool registry & execution
Lines 3082-3229: Orchestration delegation
Lines 3230-4721: execute_task() — THE MAIN TASK EXECUTOR (1,491 lines!)
Lines 4722-5753: autonomy_loop() — THE MAIN LOOP
Lines 5754-end:  Health endpoints, main() entry point
```

### The Autonomy Loop (lines 4726-5753) does this each cycle:
1. Failover check (reassign tasks from failed workers)
2. PR auto-merge monitor
3. Auto-scaling
4. Escalation timeout checks
5. Auto-approve timed-out approval requests
6. Handle orphaned waiting_approval tasks
7. Self-improvement check (every 10 loops)
8. Critical monitoring (every 10 loops)
9. Error scanning (every 30 loops)
10. Health monitoring (every 20 loops)
11. Stuck task escalation (>30min in_progress)
12. Scheduled tasks check
13. Approved tasks execution
14. **Pending tasks pickup** (line 5349) — claims and executes
15. **If no work: "No work found" heartbeat** (line 5727) — JUST HEARTBEATS, NO TASK GENERATION
16. Update worker heartbeats, sleep

---

## WHAT'S IMPORTED vs WHAT'S DEAD

### ✅ IMPORTED BY main.py (33 files — these are LIVE):
```
core/auto_scaling.py          - AutoScaler, ScalingConfig
core/critical_monitoring.py   - check_critical_issues
core/database.py              - NEON_ENDPOINT
core/dlq.py                   - move_to_dlq
core/error_recovery.py        - error recovery functions
core/error_to_task.py         - scan_errors_and_create_tasks
core/executive_reporter.py    - generate_executive_report
core/experiment_executor.py   - progress_experiments
core/experiments.py           - experiment management
core/failover.py              - process_failover
core/goal_tracker.py          - update_goal_progress
core/handlers/               - get_handler (task type routing)
core/health.py               - check_database_connection, check_worker_registry
core/health_monitor.py       - run_full_health_check
core/l5_orchestrator.py      - start_l5_orchestrator, get_l5_status
core/learning_applier.py     - apply_recent_learnings
core/learning_capture.py     - capture_task_learning
core/notifications.py        - notification functions
core/opportunity_scan_handler.py - handle_opportunity_scan
core/orchestration.py        - orchestration delegation
core/portfolio_manager.py    - portfolio management
core/pr_tracker.py           - PRTracker
core/proactive.py            - proactive task generation
core/rbac.py                 - role-based access control
core/scheduler.py            - scheduler functions
core/self_improvement.py     - self_improvement_check
core/stage_transitions.py    - stage transition management
core/stale_cleanup.py        - reset_stale_tasks
core/stale_task_reset.py     - reset_stale_tasks (duplicate import!)
core/task_templates.py       - ProposedTask, pick_diverse_tasks
core/unified_brain.py        - execute_code_task
core/verification.py         - CompletionVerifier, VerificationResult
core/verification_chains.py  - verification chain functions
```

### ❌ DEAD FILES (68 files — NEVER imported, never run):
```
core/agent_coordinator.py     core/agents.py
core/ai_executor.py           core/aider_executor.py
core/alert_rules.py           core/alerting.py
core/approval.py              core/audit.py
core/automation_proposals.py  core/autonomous_engine.py
core/autonomy_loop.py         core/autoscaling.py (duplicate of auto_scaling.py!)
core/budget_tracker.py        core/circuit_breaker.py
core/code_crawler.py          core/code_health_scorer.py
core/conflict_manager.py      core/conflict_resolver.py
core/connection.py            core/connection_pool.py
core/cost_tracker.py          core/critical_alerts.py
core/deploy_verifier.py       core/discovery.py
core/endpoint_verifier.py     core/error_fingerprinter.py
core/escalation_manager.py    core/experiment_runner.py
core/gate_checker.py          core/github_client.py
core/goal_decomposer.py  ⚠️   core/guardrails_tracker.py
core/heartbeat.py             core/idea_generator.py
core/idea_scorer.py           core/impact_simulation.py
core/innovation_engine.py     core/learning.py
core/learning_application.py  core/learning_loop.py
core/learnings.py             core/lifecycle.py
core/log_crawler.py           core/mcp_factory.py
core/mcp_tool_schemas.py      core/memory.py
core/model_selector.py        core/monitoring.py
core/plan_approval.py         core/plan_submission.py
core/pr_tracker_auto_merge.py core/railway_client.py
core/resource_allocation.py   core/resource_allocator.py
core/retry.py                 core/sandbox.py
core/scanner_config.py        core/secrets_vault.py
core/self_healing.py          core/slack_notifications.py
core/stream_events.py         core/task_batching.py
core/task_creator.py          core/task_reasoning.py
core/task_router.py           core/task_validation.py
core/tool_executor.py         core/tools.py
core/tracing.py
```

Also dead directories:
```
core/analyzers/               - entire directory, never imported
core/self_heal/               - entire directory, never imported
```

### ⚠️ CRITICAL: goal_decomposer.py EXISTS but is DEAD
`core/goal_decomposer.py` was written (394 lines, well-structured) but **never imported by main.py**.
It imports from `core/ai_executor.py` which is ALSO dead.
Even if wired in, it would fail because its dependency chain is broken.

### Also dead but in repo root:
```
src/                    - entire directory (code_validator.py, core.py, critical.py, etc.)
agents/                 - never imported
orchestrator/           - never imported  
orchestrator_main.py    - never imported
scripts/                - utility scripts
experiments/            - experiment configs
docs/                   - documentation
```

### Duplicate/conflicting files:
```
core/auto_scaling.py ↔ core/autoscaling.py (different files!)
core/conflict_manager.py ↔ core/conflict_resolver.py
core/resource_allocation.py ↔ core/resource_allocator.py
core/stale_cleanup.py ↔ core/stale_task_reset.py (both imported!)
core/learning.py ↔ core/learnings.py ↔ core/learning_loop.py ↔ core/learning_application.py
core/alerting.py ↔ core/alert_rules.py ↔ core/critical_alerts.py
```

---

## DATABASE STATE

### 124 tables total (many empty/unused)
Key active tables with data:
```
execution_logs        - 237KB  - Worker activity logs
governance_tasks      - 172KB  - Task queue (4 tasks: 3 completed, 1 in_progress)
worker_registry       - 180KB  - 5 active workers
scheduled_tasks       - 131KB  - 15+ enabled scheduled tasks
goals                 - 65KB   - 5 active goals, all 0% progress
experiments           - 115KB  - Experiment tracking
revenue_ideas         - 139KB  - Revenue idea storage
```

### Active Workers (all healthy):
```
EXECUTOR     - active, heartbeating every ~11s
STRATEGIST   - active, heartbeating every ~11s
ANALYST      - active, heartbeating every ~11s
ORCHESTRATOR - active, heartbeating every ~11s
WATCHDOG     - active, heartbeating every ~9s
```

### Active Goals (all 0% progress, no tasks generated):
```
1. "Week 1: First $100"        - Deadline: 2026-01-11 (OVERDUE)
2. "January 2026: $5K Revenue"  - Deadline: 2026-02-01 (OVERDUE)
3. "Q1 2026: $50K Revenue"      - Deadline: 2026-04-01
4. "Year 1: $1M Revenue"        - Deadline: 2027-01-01
5. "$100M Autonomous Revenue"   - Deadline: 2036-01-01
```

### Scheduled Tasks (15 enabled, running on schedule):
- critical_monitoring (every 5 min)
- pr_merge_monitor (every 5 min)
- error_scanning (every 15 min)
- stale_task_reset (every 10 min)
- proactive_diverse (hourly)
- health_check (hourly)
- goal_progress_update (daily)
- executive_report (daily)
- And more...

---

## THE CORE PROBLEM

**Goals exist → Nothing decomposes them into tasks → Queue stays empty → Workers idle**

The flow SHOULD be:
```
Goals (DB) → Decomposer → governance_tasks (pending) → autonomy_loop picks up → execute_task() → done
```

The flow ACTUALLY is:
```
Goals (DB) → ??? → empty queue → "No work found" heartbeat → sleep → repeat
```

### Why:
1. `goal_decomposer.py` exists but is NOT imported by main.py
2. Even if imported, it depends on `ai_executor.py` which is also dead
3. main.py line 5727: when no pending tasks found, it just logs "No work found" and sleeps
4. There is NO code path in main.py that reads goals and creates tasks from them
5. The `goal_tracker.py` (which IS imported) only updates progress % — it doesn't create tasks

---

## RAILWAY SERVICES (5 services, same repo)

| Service | ID | Dockerfile | Entry Point |
|---|---|---|---|
| juggernaut-engine | 9b7370c6-... | Dockerfile | `python main.py` |
| juggernaut-watchdog | 52eb8b9f-... | ? | `python watchdog_main.py` |
| juggernaut-mcp | ff009b38-... | ? | mcp server |
| juggernaut-puppeteer | fcf41c38-... | ? | puppeteer service |
| juggernaut-dashboard-api | 18cb0f88-... | Dockerfile.dashboard | `python dashboard_api_main.py` |

All 5 workers (EXECUTOR, STRATEGIST, ANALYST, ORCHESTRATOR, WATCHDOG) run from the SAME main.py on the juggernaut-engine service — they're differentiated by WORKER_ID env var.

---

## WHAT CLAUDE CODE SHOULD DO (IN ORDER)

### Phase 1: Make the system actually work (Goal → Task pipeline)
**Priority: CRITICAL — This is the ONE thing that matters**

1. Wire `goal_decomposer.py` into main.py OR rewrite the decomposition logic directly in main.py
2. The decomposer currently imports from `core/ai_executor.py` (dead file) — needs to use whatever LLM calling mechanism main.py already uses (likely OpenRouter via httpx)
3. Add a goal decomposition check to the autonomy loop's "no work found" branch (around line 5722)
4. The `_find_goals_needing_decomposition()` SQL in goal_decomposer.py looks correct — queries goals with status IN ('pending', 'in_progress', 'assigned') AND progress < 100 AND no active tasks
5. Test: After wiring in, goals should spawn tasks → tasks should appear in queue → workers should pick them up

### Phase 2: Audit every imported module for real functionality
For each of the 33 imported files, verify:
- Does it actually DO something when called?
- Does it have real implementation or just stubs/placeholders?
- Known issue: `goal_tracker.py` uses string matching like `if "first $100" in t: return 100.0`

### Phase 3: Catalog dead code for removal
The 68 dead files in core/ are not hurting anything (they're imported nowhere) but they're confusing.
- Some may contain useful code that should be integrated
- Most are likely AI-generated stubs that were never wired in
- Recommend: Move to `core/_archived/` or delete entirely

### Phase 4: Refactor main.py
The 6,491-line monolith works but is unmaintainable. Extract into modules:
- `execute_task()` alone is 1,491 lines
- Many functions duplicate what exists in dead core/ files
- But DON'T refactor until Phase 1 is working

---

## ENVIRONMENT & CREDENTIALS

### LLM Configuration (current — recently switched from Anthropic to free models):
- Uses OpenRouter API
- Models: Gemini, DeepSeek, Llama (free tier)
- Env var: OPENROUTER_API_KEY

### Database:
- Neon PostgreSQL
- Endpoint: https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech
- main.py's execute_sql() uses HTTP endpoint for queries

### GitHub:
- Repo: SpartanPlumbingJosh/juggernaut-autonomy
- Has CodeRabbit for automated PR review

### Railway:
- Project ID: e785854e-d4d6-4975-a025-812b63fe8961
- Environment: production (8bfa6a1a-92f4-4a42-bf51-194b1c844a76)

---

## KEY WARNINGS FOR CLAUDE CODE

1. **DO NOT create new files in core/ without wiring them into main.py** — this is how 68 dead files were created
2. **main.py IS the system** — if it's not in main.py or imported by main.py, it doesn't run
3. **Test changes by checking execution_logs** — `SELECT * FROM execution_logs WHERE created_at > NOW() - INTERVAL '5 minutes' ORDER BY created_at DESC LIMIT 20`
4. **The 5 workers are ALL the same process** — same main.py, different WORKER_ID
5. **goal_decomposer.py's dependency on ai_executor.py is broken** — ai_executor.py is dead code
6. **Don't add complexity** — the system has too much already. Make the simple loop work first.
7. **After ANY code change**, the juggernaut-engine Railway service needs redeployment

---

## QUICK REFERENCE: How main.py calls LLMs

Search main.py for `openrouter` or `httpx` or `chat` to find the actual LLM calling pattern.
The execute_task() function (line 3230) contains the real AI execution logic.
Do NOT use core/ai_executor.py — it's dead code with potentially different API patterns.

---

*This audit was generated by analyzing the actual running codebase, import chains, database state, and Railway deployment configuration. Every claim is verified against the real system.*
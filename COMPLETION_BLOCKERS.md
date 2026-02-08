# COMPLETION_BLOCKERS

This document is a diagnostic audit of what is currently preventing **JUGGERNAUT** (this repo) from behaving like a fully autonomous, revenue-generating system.

It is intentionally **non-prescriptive** (no implementation work here yet). It enumerates:

- Critical blockers
- Missing/partial handlers
- Stubbed code paths
- Broken pipelines (work starts but can’t finish)
- Recommended fix order

---

## Critical Blockers (must fix for autonomy)

### 1) Most task types are not executable (fallback to LLM text)

**Where:** `core/handlers/__init__.py`, `core/handlers/ai_handler.py`, `main.py` (unknown task fallback)

- The handler registry only contains:
  - Real-ish handlers: `analysis`, `database`, `research`, `scan`, `test`
  - Everything else maps to `AIHandler` (`workflow`, `planning`, `design`, `development`, `integration`, `content_creation`, etc.)
- `AIHandler` does **not** execute tools, does **not** create tasks, does **not** update DB state beyond returning a JSON blob.

**Impact:** Any task type routed to `AIHandler` can “succeed” while doing **no real work**, producing “fake completion” risk.

**Evidence:** `core/handlers/ai_handler.py` only calls `AIExecutor.chat(...)` and returns `HandlerResult(success=...)` based on the model’s JSON.

---

### 2) Two competing “tool frameworks”: one real-ish, one stubby

**Where:**
- `main.py` implements its own `execute_tool(...)` and `_execute_*_tool(...)` helpers.
- `core/tools.py` implements a fuller registry + execution wrapper with a `Tool` class.

**Problem:**
- `main.py`’s `execute_tool(...)` ultimately dispatches to `_execute_slack_tool`, `_execute_database_tool`, `_execute_http_tool` which are **placeholders** (they return `{status: "executed"}` without doing the operation).
- `core/tools.py` contains a more complete abstraction, but its built-ins are also largely placeholders (`WebSearchTool` explicitly says it is placeholder).

**Impact:** “workflow” and “tool_execution” tasks often can’t produce external side effects (send messages, call ServiceTitan, place ads, buy domains, etc.).

---

### 3) Experiments are detected but not progressed (hard stub)

**Where:** `core/experiment_executor.py`

- The scheduled experiment check calls `progress_experiments(...)` (wired in `main.py`).
- `progress_experiments(...)` logs:
  - `experiment.progress_stub` (warn)
  - returns `experiments_progressed: 0`

**Impact:** the system can have experiments in `running` status forever, with no automated iteration, measurement, or conclusion.

**Evidence:** `core/experiment_executor.py` explicitly logs “Experiment progression stub: running experiments detected but no handlers are configured”.

---

### 4) Revenue/scan paths are mostly “paperwork”, not execution

There are two scan paths:

- `task.task_type == "scan"` in `main.py` is effectively a **no-op** (it logs “Scan completed - check external systems for results”).
- `core/handlers/scan_handler.py` has some DB scanning, but external-facing scans like `expired_domains` and `market_trends` return empty lists (placeholders).
- `core/proactive.py` describes ServiceTitan/Angi scanning but explicitly says integrations are “placeholder”.

**Impact:** revenue generation is not wired to any real acquisition/execution system.

---

### 5) Handler coverage mismatch vs schema/task taxonomy

**Where:** `inspect_governance_tasks_columns.json` shows `governance_tasks.task_type` is a free-form string and the schema supports rich execution metadata.

But actual execution support is narrow:

- `main.py` has explicit branches for a limited set of types.
- `core/handlers/__init__.py` covers only a small set.
- Everything else becomes `AIHandler` (LLM response) or goes to `waiting_approval`.

**Impact:** autonomy stalls or “pretends to finish” depending on task type.

---

## Missing Handlers (task types with no real implementation)

### Handler registry coverage

**Where:** `core/handlers/__init__.py`

Registered handler keys:

- `ai` (LLM-only)
- `analysis` (real DB queries)
- `audit` (alias to `analysis`)
- `reporting` (alias to `analysis`)
- `database` (DB query execution w/ read-only enforcement)
- `research` (partially real: depends on external keys/services)
- `scan` (partially real: DB scan works; external scans are placeholder)
- `test` (DB queries)
- `workflow` (LLM-only)
- `content_creation` (LLM-only)
- `development` (LLM-only)
- `integration` (LLM-only)
- `planning` (LLM-only)
- `design` (LLM-only)

Everything else present in tasks or implied by routing tables lacks a concrete handler.

### Task types implied by routing but not implemented

**Where:** `main.py` routing dicts:
- `TASK_TYPE_TO_WORKER`
- `WORKER_ROUTING`

Examples of “taxonomies” that appear but are not actually executable (no matching main branch + no handler):

- `report`
- `metrics`
- `metrics_analysis`
- `report_generation`
- `pattern_detection`
- `goal_creation`
- `opportunity_scoring`
- `experiment_design`
- `error_detection`
- `execute`

These will fall into “unknown task type → handler lookup → fallback to AIHandler” path.

---

## Stubbed Code (exists but doesn’t do real work)

### 1) `AIHandler` (black hole)

**Where:** `core/handlers/ai_handler.py`

- Returns model-generated JSON.
- Has no enforcement that any work occurred.
- Does not call tool systems, does not create PRs, does not interact with MCP.

### 2) `main.py` tool execution placeholders

**Where:** `main.py`

- `_execute_slack_tool`, `_execute_database_tool`, `_execute_http_tool` are placeholders.
- For unknown tool types, it returns `{status: "executed"}`.

### 3) Experiment progression

**Where:** `core/experiment_executor.py`

- Detects running experiments and logs stub warning.

### 4) Scan handler external scans

**Where:** `core/handlers/scan_handler.py`

- `_scan_expired_domains` returns `[]`
- `_scan_market_trends` returns `[]`

### 5) “tool registry” framework is not wired end-to-end

**Where:** `core/tools.py`

- Has a proper Tool abstraction, but built-ins are placeholders unless you implement actual integrations.
- Also: `main.py` doesn’t use this framework; it has its own separate tool execution mechanism.

---

## Broken Pipelines (work starts but doesn’t finish)

### 1) Code tasks: `code_fix`, `code_change`, `code_implementation`, `code_implementation` are not executed

**Symptom:** You mentioned many tasks in the DB are `code_fix`, `code_change`, `code_implementation`, etc.

**What the code supports today:**

- `main.py` has a special branch only for `task.task_type == "code"`.
- There is no corresponding branch for `code_fix`, `code_change`, `code_implementation`.
- `core/handlers/__init__.py` has no `code*` handlers.

**Result:** those task types fall into the unknown-type handler path and are handled by `AIHandler` (LLM JSON), not by the code executor.

### 2) Code tasks: PR creation is real, but merge/completion depends on external conditions

**Where:**
- PR creation: `src/task_executor_code.py` → `src/github_automation.py`
- Task deferral: `main.py` sets `status = awaiting_pr_merge`
- PR tracking: `core/pr_tracker.py` and `pr_tracking` table
- PR completion: `src/scheduled/pr_monitor.py` and also `main.py` has a PR auto-merge loop block.

**What works:**
- A `code` task can:
  - create a branch
  - commit generated code
  - open a PR
  - update task to `awaiting_pr_merge`

**Where it breaks in practice (likely blockers):**
- Requires **GITHUB_TOKEN** with correct repo permissions.
- Requires **OPENROUTER_API_KEY** to generate code.
- PR merge is not guaranteed:
  - Auto-merge requires CodeRabbit approval and checks to pass, plus allowlist settings.
  - If CodeRabbit isn’t installed or doesn’t “approve” via GitHub review API, merge never triggers.
  - If checks don’t exist or never pass, merge never triggers.
  - If PR is not mergeable, task fails.

### 3) Research tasks can stall due to missing external services

**Where:** `core/handlers/research_handler.py`

- Web search requires `PERPLEXITY_API_KEY`.
- Page fetching requires `PUPPETEER_URL` and optional `PUPPETEER_AUTH_TOKEN`.

Without these, ResearchHandler falls back to “manual research required” records.

### 4) Proactive generation creates tasks that may not be executable

**Where:** `main.py::_maybe_generate_diverse_proactive_tasks`, `core/task_templates.py`

- It creates tasks of types: `analysis`, `workflow`, `scan` (and occasionally maps some to `workflow`).
- `workflow` uses `AIHandler` when it has no explicit steps.
- `scan` in `main.py` is a no-op; `scan` handler is only used if dispatched via handlers rather than the main branch.

Net effect: proactive generation can keep the queue “busy” with tasks that don’t produce revenue.

---

## Findings by Requested Investigation Areas

### 1) Handler Coverage Gap

**Registered task types:** see `core/handlers/__init__.py`.

**Fallback behavior:**

- In `main.py`, unknown types attempt `get_handler(task.task_type)`.
- If no handler exists, it falls back to `get_handler("ai")`.
- Only if handler dispatch fails entirely does it put the task into `waiting_approval`.

**AIHandler reality check:** It is *not* tool execution; it is LLM JSON generation.

### 2) Code Task Execution

**Actual handler path for code work:**

- Only `task_type == "code"` triggers real code execution.
- Code executor is real in the sense that it:
  - calls OpenRouter to generate code (`src/code_generator.py`)
  - uses GitHub API to create branches/commits/PRs (`src/github_automation.py`)

**Lifecycle:**

- Task claimed → status becomes `in_progress`.
- `main.py` moves it to `awaiting_pr_merge` before running executor.
- Executor generates code and opens PR.
- Task is deferred (kept `awaiting_pr_merge`) until:
  - PR is merged (via auto-merge loop or scheduled PR monitor), then task becomes `completed`.

**Breakdown:**

- If tasks are `code_fix`/`code_change`/`code_implementation`, they never reach the code executor.
- If GitHub/OpenRouter tokens missing, code execution fails.
- If review/merge automation is not configured, tasks can stay `awaiting_pr_merge` indefinitely.

### 3) Revenue/Experiment Execution

- Experiments table exists and contains running experiments (see `inspect_experiments.json`).
- The experiment progress driver is stubbed (`experiment.progress_stub`).

What it would take to make experiments do something:

- A real experiment runner that:
  - selects experiments in `running`
  - chooses the next “iteration task” based on experiment config
  - executes via real tools (ads, domains, email, integrations)
  - records metrics (`experiment_metric_points`)
  - increments iterations / concludes / triggers rollback

### 4) Proactive Generation Quality

**Strengths:**
- It does enforce dedupe by `dedupe_key` and title caps.

**Weaknesses:**
- It primarily produces `analysis` and `workflow` tasks.
- `workflow` tasks without steps use `AIHandler` (LLM-only).
- Revenue category templates (domain flips) use `scan` which is placeholder in both `main.py` and handler.

### 5) The AIHandler Black Hole

`AIHandler` is a “text completion handler”, not an executor.

- It can report `success=true` with a summary.
- It does not verify side effects.
- It does not tie into tool executions.

This creates a systemic risk: the dashboard can show “tasks completed” without any actual work performed.

---

## Recommended Fix Order (prioritized)

1. **Unify execution model**
   - Decide whether the canonical execution mechanism is:
     - `main.py` branches, or
     - `core/handlers/*`, or
     - `core/tools.py` tool registry.
   - Right now you have all three; they disagree and have placeholders.

2. **Eliminate fake-success pathways**
   - `AIHandler` should not be able to mark tasks successful unless it produces verifiable artifacts (tool execution IDs, PR URLs, DB changes, etc.).

3. **Make all code task types route to the code executor**
   - Map `code_fix`, `code_change`, `code_implementation` → `code` (or implement explicit handlers).

4. **Make tools real (minimum viable revenue actions)**
   - Implement at least one revenue-capable tool path end-to-end (e.g., ServiceTitan read → create follow-up tasks → send outbound via email/SMS, or domain flipping with real registrar APIs).

5. **Replace `experiment.progress_stub` with a real experiment progression loop**
   - The experiment framework exists; it needs an executor that creates/dispatches tasks and uses metric points.

6. **Tighten proactive generation to only create executable tasks**
   - Ensure proactive tasks are restricted to task types with real handlers/tools.

---

## Appendix: Notable Observations

- There are **hardcoded Neon DB credentials** in several modules (`core/experiments.py`, `core/orchestration.py`, etc.). This is a security and deployment risk.
- There are multiple DB access layers (`core.database.query_db`, ad-hoc HTTP in other modules). This increases drift and breakage.
- `src/governance_tasks.py` appears to be a separate SQLite governance task system (likely legacy/tests) and is not the same as the Neon-backed `governance_tasks` table used by `main.py`.

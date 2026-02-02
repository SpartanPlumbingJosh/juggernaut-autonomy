# WIRING_MAP (Canonical Runtime Paths)

This document is the canonical reference for which subsystems are *actually used* at runtime vs legacy/unused modules.

## Scanning

**Canonical:** `core/opportunity_scan_handler.py`

- **Scheduled scan dispatch (task_type = opportunity_scan)**
  - `main.py` (around lines 5068-5079) runs scheduled tasks and calls `handle_opportunity_scan(...)` when `sched_task_type == "opportunity_scan"`.
- **Governance task dispatch (task.task_type = opportunity_scan)**
  - `main.py` (around lines 3351-3374) calls `handle_opportunity_scan(...)` when executing an actual governance task of type `opportunity_scan`.
- **Scan → task conversion**
  - `core/opportunity_scan_handler.py` (around lines 88-136) creates `evaluation` tasks for qualified opportunities.

**Legacy / not canonical:** `core/handlers/scan_handler.py`

- Implements a separate `task_type = "scan"` handler with placeholder scan implementations.
- This path exists but is not the canonical scan pipeline.

## Experiments

**Canonical progress loop:** `core/experiment_executor.py`

- **Scheduled experiment progress**
  - `main.py` (around lines 5103-5107) runs scheduled tasks and calls `progress_experiments(...)` when `sched_task_type == "experiment_check"`.
- **Progress cycle + task creation**
  - `core/experiment_executor.py` (around lines 482-565) `progress_experiments(...)` progresses running experiments and logs `experiment.progress_cycle_complete`.
  - `core/experiment_executor.py` (around lines 253-333) `create_task_for_experiment(...)` creates governance tasks and logs `experiment.task_creation_failed` on failures.
  - `core/experiment_executor.py` (around lines 196-207) `classify_experiment(...)` determines experiment type and can emit `experiment.unknown_type` when classification fails.

**Framework module (non-canonical for progress loop):** `core/experiments.py`

- Contains a broader experimentation framework and schema helpers.
- Not the canonical scheduled “progress engine” path today.

## Resource Allocation

**Canonical tracking implementation:** `main.py`

- **Create allocation record on claim**
  - `main.py` (around lines 2399-2456) `allocate_task_resources(...)` inserts into `resource_allocations`.
  - `main.py` (around lines 4930-4934) calls `allocate_task_resources(...)` after a task is claimed.
- **Update usage on completion**
  - `main.py` (around lines 2467-2495) `update_resource_usage(...)` marks allocation completed.
  - `main.py` (around lines 4979-4984) calls `update_resource_usage(...)` after success.
- **Release on failure**
  - `main.py` (around lines 2498-2531) `release_allocation(...)` marks allocation released.
  - `main.py` (around lines 4421-4422) calls `release_allocation(...)` on task failure/exception.

**IMPORTANT:** Resource allocation is **tracking-only** right now (no enforcement gate).

**Non-canonical / currently unused allocators:**

- `core/resource_allocator.py` (advanced async ROI/budget allocator)
- `core/resource_allocation.py` (alternate allocator implementation)
- `src/wire.py` (time-budget allocator for task orchestration)

These are not the canonical runtime path for allocations today.

## Puppeteer / Web Browsing

**Research handler integration:** `core/handlers/research_handler.py`

- Reads `PUPPETEER_URL` and `PUPPETEER_AUTH_TOKEN` from environment.
- Logs `handler.research.puppeteer_unconfigured` when `PUPPETEER_URL` is missing.
- Calls `${PUPPETEER_URL}/action` for browser actions.

**Service implementation:** `services/puppeteer/server.py`

- Exposes `/health` and `/action` endpoints.

## Neural Chat Tool Surface

**Tool schemas exposed to the Brain / Neural Chat:** `core/mcp_tool_schemas.py`

- `BRAIN_TOOLS` is the authoritative list.
- L4/L5 systems exist but are not first-class tools yet; they currently run via scheduled/background loops.

Planned wiring work is tracked in PR-2 (Neural Chat tools) to make learning/experiments/scanning/puppeteer callable directly.

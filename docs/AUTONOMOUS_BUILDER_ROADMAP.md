# AUTONOMOUS BUILDER ROADMAP (2026-02-01)

This roadmap turns the audit findings into an execution plan focused on **wiring + tightening** (not rebuilding).

## North Star Definition
“Autonomous Builder” means:
- The system can take a well-scoped code task
- Modify the repo (write files)
- Open a PR with tests
- Get it reviewed (CodeRabbit + checks)
- Merge it
- Mark the governance task complete **only after merge**

---

## Current Reality (baseline)
What works today:
- Engine code executor creates branches, commits, and PRs.
  - `juggernaut-autonomy/main.py` → `src/task_executor_code.py`
- PR monitoring can mark tasks completed when PR is merged.
  - `src/scheduled/pr_monitor.py`

What blocks the autonomous builder path:
- Neural Chat cannot reliably take code-writing actions due to tool schema restrictions.
  - `core/mcp_tool_schemas.py`
- Completion semantics allow tasks to be marked `completed` with PR created but not merged.
  - `core/verification.py` returns `(True, 'pr_created')` for unmerged PR URLs

---

## Milestones

### Milestone 0 (Integrity): Make “completed” mean “merged” for code tasks
Outcome:
- No more “evidence theater” completions for code.
- Metrics reflect actual delivered code.

Work:
- Tighten evidence policy so PR URLs without merge do not pass completion for code/github tasks.
- Ensure code tasks remain `awaiting_pr_merge` until PR monitor confirms merge.

Touchpoints:
- `core/verification.py`
- `main.py:update_task_status(...)`
- `src/scheduled/pr_monitor.py` (already correct)


### Milestone 1 (Wiring): Give Neural Chat a build capability
Two options:

#### Option 1A (quick win): Expose GitHub write tools to the Brain tool schema
Outcome:
- Neural Chat can write files and open PRs through MCP tools.

Work:
- Add `github_put_file` (and optionally `github_merge_pr`) to `core/mcp_tool_schemas.py`.

Pros:
- Minimal engineering.

Cons:
- Encourages low-level multi-step LLM-driven git operations.


#### Option 1B (preferred): Expose a single “execute code task” tool wrapper
Outcome:
- Neural Chat can trigger the proven code executor pipeline with one tool call.

Work:
- Add a Brain-exposed tool that calls `src/task_executor_code.execute_code_task(...)`.
- Store result in `tool_executions` and link to task.

Pros:
- Consistent PR creation behavior.
- Avoids LLM manually chunking files/commits.
- Centralizes guardrails.

Cons:
- Slightly more engineering than 1A.


### Milestone 2 (Unification): Reduce stack divergence
Outcome:
- One authoritative code shipping path.

Work:
- Decide whether code shipping is:
  - “MCP primitive writes” (file-level tools)
  - or “code executor pipeline” (preferred)
- Make the other path call into the authoritative path.


### Milestone 3 (Self-building): Enable JUGGERNAUT to implement its own L4/L5 features safely
Outcome:
- JUGGERNAUT can ship incremental improvements to itself via PRs.

Required guardrails:
- Completion integrity (Milestone 0)
- Scoped credentials + tool allowlists
- Mandatory PR checks and CodeRabbit approval
- Small change budgets / staged rollouts

---

## Recommended Implementation Sequence
1. Milestone 0 (tighten completion semantics)
2. Milestone 1B (expose code executor wrapper to Neural Chat)
3. Milestone 1A (optional; only if needed for edge cases)
4. Milestone 2 (unify stacks)
5. Milestone 3 (self-building loop)

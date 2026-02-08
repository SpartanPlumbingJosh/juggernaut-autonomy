# Aider Integration Setup

## What It Does

Aider replaces the blind `CodeGenerator` as the primary code generation engine.

```
Old: Task → LLM prompt → raw code blob → GitHub API commit → PR
New: Task → Aider clones repo → reads context → targeted edits → git commit → push → PR
```

**Key advantages:**
- Reads existing code before making changes (repo map)
- Makes targeted edits instead of generating entire files
- Auto-commits with meaningful messages
- Can iterate on code review feedback

## How It Works

1. `CodeTaskExecutor.execute()` tries Aider first via `_try_aider()`
2. If Aider CLI is installed → clone repo, create branch, run Aider, push, create PR
3. If Aider is not installed → falls back to legacy `CodeGenerator` (blind LLM prompting)

## Task Payload Fields

When creating code tasks, these payload fields control Aider behavior:

| Field | Type | Description |
|---|---|---|
| `target_repo` | string | Repository to edit (e.g., "owner/repo") |
| `target_files` | string[] | Files Aider should edit (added to chat) |
| `read_only_files` | string[] | Files Aider should read for context only |

Example task payload:
```json
{
  "target_repo": "juggernaut-autonomy",
  "target_files": ["core/failover.py"],
  "read_only_files": ["core/database.py", "core/retry.py"],
  "description": "Add circuit breaker pattern to failover.py"
}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AIDER_MODEL` | `openai/gpt-4o-mini` | Model for Aider to use |
| `AIDER_EDIT_FORMAT` | `diff` | Edit format (diff, whole, udiff) |
| `AIDER_TIMEOUT_SECONDS` | `300` | Max time per Aider run |
| `AIDER_MAX_RETRIES` | `2` | Retries on failure |
| `AIDER_WORKSPACE` | `/tmp/juggernaut-repos` | Directory for cloned repos |
| `GITHUB_TOKEN` | (required) | Token for clone/push operations |
| `GIT_USER_NAME` | `JUGGERNAUT Engine` | Git commit author name |
| `GIT_USER_EMAIL` | `engine@juggernaut.dev` | Git commit author email |

If `LLM_API_BASE` is set (LiteLLM proxy), Aider will route through it automatically.

## Review Feedback Iteration

When CodeRabbit posts review comments on a PR:

1. PR tracker detects unresolved review comments
2. Calls `AiderExecutor.run_with_review_feedback()` with the review text
3. Aider checks out the existing branch, makes fixes, pushes
4. CodeRabbit re-reviews automatically

## Verifying Aider Is Working

Check the execution logs for these actions:
- `code_task.aider_mode` — Aider path was selected
- `code_task.aider_unavailable` — Fell back to CodeGenerator
- `code_task.pr_created` — PR created (will say "Aider" in message)

## Rollback

To disable Aider and use the legacy CodeGenerator:
```
AIDER_DISABLED=1
```
Or simply don't install `aider-chat` — the system auto-detects and falls back.

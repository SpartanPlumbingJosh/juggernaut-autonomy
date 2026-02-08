# Aider Self-Fix Service

Dedicated Railway service for autonomous bug fixing using Aider CLI.

## Architecture

**Isolated Service Approach:**
- Runs in dedicated Railway container (not in engine)
- Maintains its own repo clone
- Prevents bad fixes from crashing the engine
- Clean separation of concerns

## How It Works

1. **Error Detection:** Engine detects bug via logs/exceptions
2. **Task Creation:** Creates `code_fix` task with error details
3. **Aider Execution:** CodeFixHandler calls Aider CLI
4. **Fix Generation:** Aider analyzes code, generates fix, commits
5. **PR Creation:** Handler creates PR via GitHub API
6. **Review:** CodeRabbit reviews the fix
7. **Auto-Merge:** PR tracker auto-merges if approved
8. **Deploy:** Railway auto-deploys on merge

## Environment Variables

Required:
- `GITHUB_TOKEN` - GitHub personal access token with repo access
- `OPENROUTER_API_KEY` - For Aider's LLM calls
- `AIDER_MODEL` - Model to use (default: `openai/gpt-4o-mini`)

Optional:
- `AIDER_TIMEOUT_SECONDS` - Max execution time (default: 300)
- `AIDER_WORKSPACE` - Workspace directory (default: `/tmp/juggernaut-fixes`)

## Deployment

```bash
# Deploy to Railway
railway up --service aider

# Set environment variables
railway variables set GITHUB_TOKEN=ghp_xxx
railway variables set OPENROUTER_API_KEY=sk-xxx
```

## Test Case: Bug #14

**Error:**
```
'<' not supported between instances of 'str' and 'int'
File: core/experiment_executor.py, Line: 554
```

**Expected Fix:**
```python
retry_count = int(retry_count) if retry_count else 0
```

**Aider Command:**
```bash
aider --yes \
  --model openai/gpt-4o-mini \
  --message "Fix type comparison error: retry_count from DB is string, needs int conversion before comparing to 3" \
  core/experiment_executor.py
```

## Success Metrics

- **Fix Accuracy:** % of Aider-generated fixes that pass review
- **Time to Fix:** Error detection → PR created
- **Auto-Merge Rate:** % of fixes that auto-merge without human intervention
- **Deployment Time:** PR merged → Railway deployed

## Future Enhancements

1. **Multi-file fixes:** Handle bugs spanning multiple files
2. **Test generation:** Aider generates regression tests
3. **Rollback detection:** Auto-revert if fix causes new errors
4. **Learning loop:** Track which error patterns Aider handles best

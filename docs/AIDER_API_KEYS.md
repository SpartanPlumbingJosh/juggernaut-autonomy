# Aider API Key Configuration

## Problem

Aider is failing with "made no changes to the codebase" because it can't call an LLM.

## Required Environment Variables

Aider needs **at least one** of these API keys set in Railway:

### Option 1: OpenAI (Recommended)
```bash
OPENAI_API_KEY=sk-...
```

### Option 2: OpenRouter (Fallback)
```bash
OPENROUTER_API_KEY=sk-or-...
```

## Current Configuration

Check Railway environment variables for the **Aider service**:

```bash
railway variables list --service aider
```

## Setting the Keys

```bash
# For Aider service
railway variables set OPENAI_API_KEY=sk-... --service aider

# OR for OpenRouter
railway variables set OPENROUTER_API_KEY=sk-or-... --service aider
```

## Model Configuration

Aider will use these models by default:

- **OpenAI:** `gpt-4o-mini` or `gpt-4o`
- **OpenRouter:** Routes to best available model

Override with:
```bash
railway variables set AIDER_MODEL=openai/gpt-4o-mini --service aider
```

## Verification

After setting keys, check Aider logs:

```bash
railway logs --service aider --filter "aider"
```

Look for:
- ✅ "Using model: gpt-4o" or "Using model: gpt-4o-mini"
- ❌ "API key not found" or "Authentication failed"

## Why Aider Failed

**Logs showed:** "Aider made no changes to the codebase"

**Root cause:** No valid API key configured, so Aider couldn't:
1. Analyze the error
2. Generate a fix
3. Create a commit

**Fix:** Set one of the API keys above and redeploy.

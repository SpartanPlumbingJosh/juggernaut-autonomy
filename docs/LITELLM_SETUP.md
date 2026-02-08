# LiteLLM Proxy Setup

## What It Does

LiteLLM sits between JUGGERNAUT workers and LLM providers. All LLM calls route through it.

```
Workers → LiteLLM Proxy → OpenRouter (primary)
                        → OpenAI (fallback)
```

**Benefits:**
- Automatic fallbacks if a provider is down
- No OpenRouter 5.5% markup on direct API calls
- Budget caps per day ($50 default)
- Latency-based routing picks the fastest healthy model
- Single endpoint to configure across all workers

## Railway Deployment

### 1. Create a new service in Railway

In the juggernaut-autonomy Railway project:
- Click "New Service" → "GitHub Repo" → select juggernaut-autonomy
- In service settings, set the **Root Directory** to `/` and **Dockerfile** to `Dockerfile.litellm`
- Or use the Railway CLI:

```bash
railway service create juggernaut-litellm
railway up --dockerfile Dockerfile.litellm
```

### 2. Set environment variables on the LiteLLM service

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter key (primary provider) |
| `OPENAI_API_KEY` | No | Direct OpenAI key (fallback) |
| `LITELLM_MASTER_KEY` | Yes | Auth key for proxy access (generate a random string) |

### 3. Get the LiteLLM internal URL

After deploy, Railway assigns an internal URL like:
```
juggernaut-litellm.railway.internal:4000
```

Or a public URL like:
```
https://juggernaut-litellm-production.up.railway.app
```

### 4. Point workers at LiteLLM

On the **juggernaut-autonomy** engine service, set:

```
LLM_API_BASE=http://juggernaut-litellm.railway.internal:4000/v1
LLM_API_KEY=<your LITELLM_MASTER_KEY>
```

On the **juggernaut-mcp** service, set the same two vars.

That's it. Workers will now route through LiteLLM automatically. No code changes needed — the env vars are already wired up.

### 5. Verify

Hit the health endpoint:
```bash
curl https://juggernaut-litellm-production.up.railway.app/health
```

Check model routing:
```bash
curl https://juggernaut-litellm-production.up.railway.app/v1/models \
  -H "Authorization: Bearer <LITELLM_MASTER_KEY>"
```

## Fallback Behavior

If OpenRouter is down or rate-limited:
1. Request automatically retries on OpenAI
2. Total retries: 2 per provider

## Budget Controls

Default: $50/day across all workers. Configurable in `litellm/litellm_config.yaml`:

```yaml
litellm_settings:
  max_budget: 50.0
  budget_duration: "1d"
```

## Rollback

To revert to direct OpenRouter (remove LiteLLM from the path):
1. Remove `LLM_API_BASE` and `LLM_API_KEY` env vars from engine + MCP services
2. Workers automatically fall back to `OPENROUTER_API_KEY` + `openrouter.ai/api/v1`

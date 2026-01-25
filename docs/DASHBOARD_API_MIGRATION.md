# Dashboard API Migration to Railway

## Problem
The dashboard API was hosted on Vercel serverless functions, causing:
- **$65 cost spike** (normally $20/month)
- $51 in "Fluid Provisioned Memory" charges from long-running functions
- Functions allocated 1GB memory by default
- Database timeouts causing functions to hang
- Infinite spinner issues on dashboard frontend

## Solution
Migrate the dashboard API from Vercel → Railway for:
- ✅ Persistent FastAPI server (no cold starts)
- ✅ Predictable costs (~$5/month vs per-request charges)
- ✅ Efficient database connection pooling
- ✅ No per-request memory charges
- ✅ Better performance for the dashboard

## Architecture

### Before
```text
Dashboard Frontend (Vercel) 
    ↓
Dashboard API (Vercel Serverless) ← $65/month, timeouts, cold starts
    ↓
Neon Database
```

### After
```text
Dashboard Frontend (Vercel) 
    ↓
Dashboard API (Railway FastAPI) ← $5/month, always-on, fast
    ↓
Neon Database
```

## Files Changed

1. **`dashboard_api_main.py`** - New FastAPI wrapper for the dashboard API
2. **`Dockerfile.dashboard`** - Docker configuration for Railway deployment
3. **`railway.dashboard.toml`** - Railway service configuration
4. **`vercel.json`** - Removed API routes (now on Railway)

## Setup Instructions

### Step 1: Set Environment Variables on Railway

The `juggernaut-dashboard-api` service needs these environment variables:

```bash
DATABASE_URL=postgresql://<username>:<password>@<host>/<database>?sslmode=require

DASHBOARD_API_SECRET=<generate a secret key>
```

**Note:** Get the actual DATABASE_URL from your Neon dashboard or environment configuration. Never commit real credentials to git.

Generate the API secret:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 2: Deploy to Railway

1. Railway will auto-detect the `Dockerfile.dashboard`
2. It will build and deploy the FastAPI service
3. Railway will provide a public URL like: `https://juggernaut-dashboard-api-production.up.railway.app`

### Step 3: Update Frontend Configuration

Update your dashboard frontend to call the Railway URL instead of Vercel:

**Before:**
```javascript
const API_URL = "https://spartan-hq.vercel.app/v1";
```

**After:**
```javascript
const API_URL = "https://juggernaut-dashboard-api-production.up.railway.app/v1";
```

### Step 4: Test the API

```bash
# Health check
curl https://juggernaut-dashboard-api-production.up.railway.app/health

# Get dashboard overview (requires API key)
curl -H "Authorization: Bearer <your-api-key>" \
  https://juggernaut-dashboard-api-production.up.railway.app/v1/overview
```

## API Endpoints

All endpoints remain the same:
- `GET /health` - Health check
- `GET /v1/overview` - Dashboard overview
- `GET /v1/revenue_summary` - Revenue summary
- `GET /v1/revenue_by_source` - Revenue by source
- `GET /v1/experiment_status` - Experiment status
- `GET /v1/experiment_details/{id}` - Experiment details
- `GET /v1/agent_health` - Agent health
- `GET /v1/goal_progress` - Goal progress
- `GET /v1/profit_loss` - Profit/loss analysis
- `GET /v1/pending_approvals` - Pending approvals
- `GET /v1/system_alerts` - System alerts

## Cost Comparison

| Platform | Before | After |
|----------|--------|-------|
| Vercel | $65/month (spike) | $0 (frontend only) |
| Railway | $0 | $5/month |
| **Total** | **$65/month** | **$5/month** |

**Savings: $60/month** 💰

## Rollback Plan

If issues arise:
1. Revert the `vercel.json` changes to restore API routes
2. Redeploy Vercel
3. Update frontend to point back to Vercel
4. Pause Railway service

## Next Steps

1. Merge this PR
2. Set environment variables on Railway
3. Deploy to Railway
4. Update frontend configuration
5. Monitor costs (should drop to ~$5/month)
6. Close PR #238 (no longer needed)

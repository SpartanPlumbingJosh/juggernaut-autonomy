# Post-API Wiring Checklist

Once the API wiring is complete, follow these steps to fully activate the system.

---

## ✅ Immediate Actions (5 minutes)

### 1. Run Revenue Generation Trigger
Execute the SQL script to start discovering opportunities:

```bash
# Connect to Neon database
psql $DATABASE_URL -f scripts/trigger_revenue_generation.sql
```

**What this does:**
- Fixes `revenue_ideas.created_at` NULL bug
- Creates 2 high-priority tasks:
  - `idea_generation` - Discovers revenue opportunities
  - `opportunity_scan` - Scans multiple sources
- Shows current state of ideas, experiments, revenue

**Expected result:** Tasks execute within 1-2 autonomy loop cycles

### 2. Set Spartan HQ Environment Variable
In Vercel dashboard for spartan-hq:

```bash
NEXT_PUBLIC_JUGGERNAUT_API_URL=https://juggernaut-dashboard-api-production.up.railway.app
```

**Then redeploy:**
```bash
cd spartan-hq
vercel --prod
```

**Expected result:** Dashboard pages fetch real data

### 3. Verify APIs Work
Test the new endpoints:

```bash
# Opportunities
curl https://juggernaut-dashboard-api-production.up.railway.app/opportunities/stats

# Revenue
curl https://juggernaut-dashboard-api-production.up.railway.app/revenue/summary

# Experiments
curl https://juggernaut-dashboard-api-production.up.railway.app/experiments/stats
```

**Expected result:** JSON responses with data

---

## 🔄 Next Steps (30 minutes)

### 4. Close the Learning Loop
Implement experiment result callback to update discovery strategy.

**File:** `core/experiment_executor.py`

Add after experiment completion:

```python
async def on_experiment_complete(experiment_id: str, result: ExperimentResult):
    """Update learning from experiment results."""
    if result.success and result.roi > 2.0:  # 200% ROI
        # Update discovery weights
        await update_discovery_weights(
            opportunity_type=experiment.opportunity_type,
            weight_adjustment=+0.1  # Increase weight for successful types
        )
        
        # Store success pattern
        await store_success_pattern(
            experiment_id=experiment_id,
            features=extract_features(experiment),
            roi=result.roi
        )
```

**Impact:** System learns from successes, not just failures

### 5. Rotate Exposed Secrets
**File:** `core/mcp_factory.py`

Move hardcoded credentials to environment variables:

```python
# BEFORE (INSECURE):
NEON_CONNECTION_STRING = "postgresql://..."
RAILWAY_API_TOKEN = "..."

# AFTER (SECURE):
NEON_CONNECTION_STRING = os.getenv("NEON_CONNECTION_STRING")
RAILWAY_API_TOKEN = os.getenv("RAILWAY_API_TOKEN")
```

**Then rotate:**
1. Generate new Neon connection string
2. Generate new Railway API token
3. Update Railway environment variables
4. Redeploy

**Impact:** Security hardening

---

## 📊 Verification (10 minutes)

### 6. Monitor First Revenue Cycle

Watch the autonomy loop execute:

```bash
# Check task execution
SELECT id, title, task_type, status, created_at, started_at
FROM governance_tasks
WHERE task_type IN ('idea_generation', 'opportunity_scan')
ORDER BY created_at DESC
LIMIT 10;

# Check generated ideas
SELECT id, title, score, status, created_at
FROM revenue_ideas
ORDER BY created_at DESC
LIMIT 10;

# Check experiments created
SELECT id, name, status, budget_allocated, created_at
FROM experiments
ORDER BY created_at DESC
LIMIT 10;
```

**Expected timeline:**
- 0-5 min: Tasks claimed and executing
- 5-10 min: Ideas generated
- 10-15 min: Ideas scored
- 15-20 min: Top ideas converted to experiments
- 20-30 min: Experiments running

### 7. Verify Spartan HQ Dashboard

Open in browser:
```
https://spartan-hq.vercel.app/opportunities
https://spartan-hq.vercel.app/revenue
https://spartan-hq.vercel.app/experiments
```

**Expected result:**
- Opportunities page shows pipeline data
- Revenue page shows $0 (for now) with MTD/QTD/YTD cards
- Experiments page shows running experiments

---

## 🎯 Success Criteria

**System is fully operational when:**
- ✅ All 3 Spartan HQ pages show real data (not "IN DEVELOPMENT")
- ✅ Revenue ideas are being generated automatically
- ✅ Experiments are being created from top ideas
- ✅ Self-improvement system is creating fix tasks from failures
- ✅ No NULL values in revenue_ideas.created_at
- ✅ No exposed secrets in code

**L5 Autonomy Status:**
- Current: 65% → Target: 75% (after these steps)
- Remaining gap: Learning loop + active revenue generation

---

## 🚨 Troubleshooting

**If APIs return 404:**
- Check the router integration was deployed
- Verify Railway deployment succeeded
- Check logs: `railway logs -s dashboard-api`

**If Spartan HQ shows errors:**
- Verify `NEXT_PUBLIC_JUGGERNAUT_API_URL` is set
- Check browser console for CORS errors
- Verify Vercel deployment succeeded

**If tasks don't execute:**
- Check autonomy loop is running: `railway logs -s juggernaut-autonomy`
- Verify tasks are in `pending` status
- Check worker is active: `SELECT * FROM worker_registry`

**If no ideas generated:**
- Check `idea_generation` handler exists
- Verify web search API is working
- Check logs for errors

---

## 📈 Next Phase: Revenue Generation

Once everything is working:

1. **Monitor first experiments** (Week 1)
   - Watch ROI metrics
   - Identify successful patterns
   - Kill failing experiments

2. **Scale successful strategies** (Week 2-4)
   - Increase budget for high-ROI experiments
   - Create variants of successful ideas
   - Automate experiment creation

3. **Reach first dollar** (Week 4-8)
   - Focus on quick-win opportunities
   - Optimize conversion rates
   - Track revenue in dashboard

**Target:** $1 → $100 → $1,000 → $10,000 MRR

---

## 🔗 Related Files

- `scripts/trigger_revenue_generation.sql` - Manual trigger script
- `docs/L5_AUTONOMY_AUDIT.md` - Current state assessment
- `docs/L5_ENTERPRISE_PLAN.md` - Full roadmap to L5
- `api/opportunities_api.py` - Opportunities endpoint
- `api/revenue_api.py` - Revenue tracking endpoint
- `api/experiments_api.py` - Experiments endpoint

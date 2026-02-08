# L5 Enterprise Implementation Summary
## Bulletproof Plan for Full Autonomy

**Status:** Ready to Execute  
**Timeline:** 3-4 weeks (160-200 hours)  
**Current Progress:** ~5% (Basic L4 features only)

---

## 🎯 Six Milestones Overview

### Milestone 1: Chat Control Plane (Week 1 - 40hrs) ⭐ FOUNDATION
**Goal:** Stop feeling blind - always know what's happening

**Backend (juggernaut-autonomy):**
- Streaming event contract: `token`, `status`, `tool_start`, `tool_result`, `budget`, `stop_reason`, `guardrails`
- Budget tracking: steps, time, retries per fingerprint
- Guardrails: failure fingerprints, no-progress detection
- Database tables: `tool_executions`, `chat_budgets`

**Frontend (spartan-hq):**
- `StatusIndicator` - Real-time status display
- `ToolTimeline` - Expandable tool execution history
- `BudgetDisplay` - Progress meters for steps/time
- `WhyIdlePanel` - Explains why system is idle
- `RunControls` - Run/Stop/Mode selector
- `GuardrailsDisplay` - Safety counters

**Success Criteria:**
- Within 5 seconds, know: what it's doing OR why it's idle
- Tool timeline shows all executions with expand/collapse
- Budget meters update in real-time
- Stop reasons are clear and actionable

---

### Milestone 2: Self-Heal Workflows (Week 2 - 40hrs)
**Goal:** One-click diagnosis + bounded repair

**Components:**
- Playbook system (max 10 steps, safe actions only)
- `DiagnoseSystemPlaybook` - Check workers, queue, errors, DB, APIs
- `RepairCommonIssuesPlaybook` - Reset blocked tasks, create fix tasks
- Database tables: `self_heal_playbooks`, `self_heal_executions`
- API endpoints: `/self-heal/diagnose`, `/self-heal/repair`, `/self-heal/auto-heal`
- Frontend: Self-Heal page with diagnosis report and repair actions

**Success Criteria:**
- One-click diagnosis produces actionable report
- Safe repairs execute automatically
- Verification confirms improvements
- Manual actions clearly flagged

---

### Milestone 3: Railway Logs Crawler (Week 2-3 - 40hrs)
**Goal:** Stop manual log babysitting

**Architecture:**
```
Railway API → Log Fetcher → Error Parser → Fingerprinter → DB Storage → Task Creator
```

**Components:**
- `RailwayLogsClient` - Fetch logs via Railway API
- `ErrorFingerprinter` - Dedupe errors by pattern
- `LogCrawlerScheduler` - Run every 5 minutes
- Database tables: `railway_logs`, `error_fingerprints`, `error_occurrences`
- Alert rules: new fingerprint, spike in rate, sustained 5xx
- Auto-create governance tasks for new error patterns

**Success Criteria:**
- HQ shows "Top errors last 1h/24h" per service
- Tasks auto-created for new error patterns
- Alerts only on meaningful changes
- No manual Railway log checking needed

---

### Milestone 4: GitHub Code Crawler (Week 3 - 40hrs)
**Goal:** Code health autopilot

**Checks:**
1. **Static Analysis** - ruff, tsc, eslint via GitHub Actions API
2. **Stale Detection** - Files/routes/tools defined but never used
3. **Contract Validation** - Frontend expects X, backend emits Y
4. **Dependency Audit** - Outdated packages, security vulnerabilities

**Components:**
- `GitHubCodeAnalyzer` - Fetch repo data, run checks
- `StaleCodeDetector` - Find unused imports, routes, tools
- `ContractValidator` - Compare API schemas
- `AutoPRGenerator` - Create PRs for mechanical fixes only
- Database tables: `code_health_reports`, `stale_code_items`
- Weekly report generation

**Success Criteria:**
- Weekly code health report
- Auto-PRs for safe fixes (imports, formatting, missing fields)
- Stale code flagged for review
- Contract mismatches detected early

---

### Milestone 5: Engine Autonomy Restoration (Week 3-4 - 40hrs)
**Goal:** Always-on but safe

**Improvements:**
1. **Unblock Rules** - Tasks that can't execute → waiting_approval
2. **Worker Rerouting** - Reroute tasks to capable workers
3. **Continuous Improvement Loop** - Logs → Tasks → Code fixes → Engine executes
4. **Scheduler Reliability** - Handle stuck tasks, timeouts, failures

**Components:**
- Enhanced `autonomy_loop` with unblock logic
- `TaskRouter` - Match tasks to capable workers
- `StuckTaskDetector` - Find and escalate stuck tasks
- Integration with Milestones 3 & 4 for auto-task creation

**Success Criteria:**
- Engine keeps moving without chat babysitting
- Blocked tasks automatically unblocked or escalated
- Workers self-assign based on capabilities
- Continuous improvement from logs/code analysis

---

### Milestone 6: OpenRouter Smart Routing (Week 4 - 20hrs)
**Goal:** Best model for the job without runaway cost

**Policy-Based Routing:**
```python
ROUTING_POLICIES = {
    "normal": {
        "provider": "openrouter/auto",
        "max_price_per_1k_tokens": 0.01,
        "max_context": 32000,
        "max_iterations": 10
    },
    "deep_research": {
        "provider": "openai/gpt-4o",
        "max_price_per_1k_tokens": 0.10,
        "max_context": 200000,
        "max_iterations": 50
    },
    "code": {
        "provider": "openai/gpt-4o",
        "max_price_per_1k_tokens": 0.03,
        "max_context": 200000,
        "max_iterations": 20
    },
    "ops": {
        "provider": "openai/gpt-4o-mini",
        "max_price_per_1k_tokens": 0.001,
        "max_context": 16000,
        "max_iterations": 5
    }
}
```

**Components:**
- `OpenRouterPolicyManager` - Select policy based on mode
- `CostTracker` - Track spending per session/mode
- `ModelSelector` - Choose model within policy constraints
- Budget enforcement at policy level

**Success Criteria:**
- Each mode uses appropriate model
- Costs stay within policy limits
- Quality maintained for each use case
- Easy to adjust policies

---

## 📊 Implementation Sequence

### Phase 1: Foundation (Week 1)
1. Milestone 1: Chat Control Plane
   - Backend streaming events
   - Frontend UI components
   - Integration and testing

### Phase 2: Observability (Week 2)
2. Milestone 2: Self-Heal Workflows
3. Milestone 3: Railway Logs Crawler (start)

### Phase 3: Intelligence (Week 3)
4. Milestone 3: Railway Logs Crawler (complete)
5. Milestone 4: GitHub Code Crawler

### Phase 4: Autonomy (Week 4)
6. Milestone 5: Engine Autonomy Restoration
7. Milestone 6: OpenRouter Smart Routing

---

## 🗂️ File Structure

```
juggernaut-autonomy/
├── api/
│   ├── brain_api.py (enhanced streaming)
│   ├── self_heal_api.py (NEW)
│   └── logs_api.py (NEW)
├── core/
│   ├── budget_tracker.py (NEW)
│   ├── guardrails_tracker.py (NEW)
│   ├── self_heal/
│   │   ├── playbooks/
│   │   │   ├── diagnose_system.py (NEW)
│   │   │   └── repair_common_issues.py (NEW)
│   ├── railway_logs/
│   │   ├── client.py (NEW)
│   │   ├── fingerprinter.py (NEW)
│   │   └── crawler.py (NEW)
│   ├── github_code/
│   │   ├── analyzer.py (NEW)
│   │   ├── stale_detector.py (NEW)
│   │   └── contract_validator.py (NEW)
│   └── openrouter/
│       ├── policy_manager.py (NEW)
│       └── cost_tracker.py (NEW)
└── docs/
    ├── L5_ENTERPRISE_EXECUTION_PLAN.md (detailed specs)
    └── L5_IMPLEMENTATION_SUMMARY.md (this file)

spartan-hq/
├── app/(app)/
│   ├── chat/
│   │   ├── components/
│   │   │   ├── StatusIndicator.tsx (NEW)
│   │   │   ├── ToolTimeline.tsx (NEW)
│   │   │   ├── BudgetDisplay.tsx (NEW)
│   │   │   ├── WhyIdlePanel.tsx (NEW)
│   │   │   ├── RunControls.tsx (NEW)
│   │   │   └── GuardrailsDisplay.tsx (NEW)
│   │   └── page.tsx (enhanced)
│   ├── self-heal/
│   │   └── page.tsx (NEW)
│   └── system-health/
│       └── page.tsx (NEW - logs/code health)
```

---

## 🗄️ Database Schema Changes

```sql
-- Milestone 1: Chat Control Plane
ALTER TABLE chat_sessions ADD COLUMN current_status VARCHAR(50);
ALTER TABLE chat_sessions ADD COLUMN current_budget_used INTEGER;
ALTER TABLE chat_sessions ADD COLUMN stop_reason VARCHAR(100);
ALTER TABLE chat_sessions ADD COLUMN guardrails_state JSONB;
ALTER TABLE chat_sessions ADD COLUMN mode VARCHAR(50);

CREATE TABLE tool_executions (...);
CREATE TABLE chat_budgets (...);

-- Milestone 2: Self-Heal
CREATE TABLE self_heal_playbooks (...);
CREATE TABLE self_heal_executions (...);

-- Milestone 3: Railway Logs
CREATE TABLE railway_logs (...);
CREATE TABLE error_fingerprints (...);
CREATE TABLE error_occurrences (...);

-- Milestone 4: GitHub Code
CREATE TABLE code_health_reports (...);
CREATE TABLE stale_code_items (...);
CREATE TABLE contract_violations (...);

-- Milestone 6: OpenRouter
CREATE TABLE openrouter_usage (...);
CREATE TABLE cost_tracking (...);
```

---

## 🚀 Getting Started

### Immediate Next Steps:
1. Review this plan and approve approach
2. Start Milestone 1 implementation
3. Set up development branches
4. Create tracking issues in GitHub

### Development Workflow:
1. Create feature branch: `feature/milestone-1-chat-control`
2. Implement backend changes first
3. Add database migrations
4. Build frontend components
5. Integration testing
6. Deploy to Railway/Vercel
7. User acceptance testing
8. Merge to main

### Testing Strategy:
- Unit tests for each new module
- Integration tests for API endpoints
- E2E tests for critical user flows
- Load testing for streaming events
- Manual QA for UI components

---

## 📈 Success Metrics

### Milestone 1:
- User can see system status within 5 seconds
- Tool timeline shows 100% of executions
- Budget meters accurate to within 1 second
- Zero "what is it doing?" questions

### Milestone 2:
- Diagnosis completes in < 10 seconds
- Repairs succeed 80%+ of the time
- Manual intervention reduced by 50%

### Milestone 3:
- 100% of errors captured from Railway
- Tasks auto-created within 5 minutes of new error
- Zero manual log checking needed

### Milestone 4:
- Weekly code health reports generated
- 90%+ of stale code detected
- Auto-PRs for 50%+ of mechanical fixes

### Milestone 5:
- Engine uptime > 99%
- Task queue never stuck > 1 hour
- Self-healing from 80%+ of issues

### Milestone 6:
- Costs stay within policy limits
- Quality maintained across modes
- Zero runaway cost incidents

---

## ⚠️ Risk Mitigation

### Technical Risks:
1. **Streaming complexity** - Mitigation: Comprehensive event schema, thorough testing
2. **Railway API rate limits** - Mitigation: Caching, exponential backoff
3. **GitHub API costs** - Mitigation: Incremental analysis, smart caching
4. **Database performance** - Mitigation: Proper indexing, query optimization

### Operational Risks:
1. **Breaking changes** - Mitigation: Feature flags, gradual rollout
2. **Data loss** - Mitigation: Backups, migration testing
3. **User confusion** - Mitigation: Clear documentation, tooltips
4. **Cost overruns** - Mitigation: Budget alerts, policy enforcement

---

## 💰 Cost Estimates

### Development:
- 160-200 hours @ $150/hr = $24,000 - $30,000

### Infrastructure (monthly):
- Railway: $20-50 (current)
- Vercel: $20 (current)
- OpenRouter: $50-200 (varies by usage)
- GitHub API: $0 (within free tier)
- **Total:** $90-270/month

### ROI:
- Reduced manual intervention: 10+ hours/week saved
- Faster issue resolution: 50% reduction in downtime
- Better decision making: Real-time visibility
- **Break-even:** 2-3 months

---

## 📞 Support & Escalation

### During Implementation:
- Daily standups to review progress
- Blockers escalated immediately
- Weekly demos of completed features

### Post-Launch:
- Monitor error rates and user feedback
- Iterate based on real usage patterns
- Continuous improvement backlog

---

**This plan is ready for execution. Let's build L5 autonomy! 🚀**

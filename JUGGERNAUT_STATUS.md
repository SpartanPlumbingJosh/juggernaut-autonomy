# JUGGERNAUT - Master Reference Document

> **Last Updated:** 2026-02-07
> **Purpose:** Single source of truth for all Claude sessions working on JUGGERNAUT
> **Update Instructions:** Any Claude session that makes significant progress should update this file and push to the repo

---

## 1. WHAT IS JUGGERNAUT

JUGGERNAUT is a general-purpose autonomous AI platform that progresses through five autonomy levels (L1-L5) — from basic conversational interfaces to full organizational orchestration. It is a self-improving system where autonomous workers claim, execute, and verify tasks without human intervention, learning from each cycle to expand their capabilities.

The platform is designed to be domain-agnostic: a single infrastructure that can manage development workflows, business operations, research pipelines, or any complex multi-agent coordination challenge. The current implementation runs on Railway (backend services), Vercel (dashboard), and Neon PostgreSQL (shared state).

**Owner:** Josh Ferguson
**Repository:** `SpartanPlumbingJosh/juggernaut-autonomy`

### Core Principles
- **Autonomy over dependency** — Every intervention should make workers more capable, not more reliant on humans
- **Evidence-based completion** — Tasks require real deliverables (merged PRs, test results, deployed endpoints), not generic "done" markers
- **Consolidation over sprawl** — Three-platform architecture (Railway/Vercel/Neon) beats scattered deployments

---

## 2. SYSTEM ARCHITECTURE

### Core Services (Railway)
| Service | ID | URL | Purpose |
|---------|-----|-----|---------| 
| juggernaut-engine | `9b7370c6-7764-4eb6-a64c-75cce1d23e06` | juggernaut-engine-production.up.railway.app | Main autonomy loop |
| juggernaut-mcp | `ff009b38-e969-4be7-9930-cd7700062be6` | juggernaut-mcp-production.up.railway.app | MCP tools server (68+ tools) |
| juggernaut-watchdog | `52eb8b9f-6920-4a49-8522-7bc4415076a7` | — | Health monitoring |
| juggernaut-puppeteer | `fcf41c38-5cc1-46ac-82f2-cf078b839786` | — | Browser automation |
| juggernaut-dashboard-api | `18cb0f88-242b-4212-82d2-070fb2f1f621` | juggernaut-dashboard-api-production.up.railway.app | Dashboard data API |

### Database (Neon PostgreSQL)
- **HTTP Endpoint:** `https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql`
- **Tables:** 69+ including `governance_tasks`, `execution_logs`, `worker_registry`, `experiments`

### Dashboard (Vercel)
- **Project:** spartan-hq
- **URL:** hq.spartan-plumbing.com
- **Status:** Factory Floor visualization live, layout + polish ongoing

### Workers
| Worker | Type | Status | Capabilities |
|--------|------|--------|--------------|
| EXECUTOR | specialist | ✅ Active | task.execute, content.create, tool.execute |
| ORCHESTRATOR | orchestrator | ✅ Active | goal.create, task.assign, worker.coordinate |
| ANALYST | specialist | ✅ Active | metrics.analyze, pattern.detect, report.generate |
| STRATEGIST | specialist | ✅ Active | goal.decompose, experiment.design |
| WATCHDOG | monitor | ✅ Active | health.check, error.detect, alert.send |

### Neural Chat System
AI-powered chat interface for querying and controlling JUGGERNAUT systems.

**Architecture:**
```
User → Dashboard frontend → Brain API → OpenRouter (function calling)
                                       → MCP Server (tool execution)
                                       → PostgreSQL (state/history)
```

**API Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/brain/consult` | POST | Main chat endpoint with tool execution |
| `/api/chat/sessions` | GET | List chat sessions |
| `/api/chat/sessions` | POST | Create new session |
| `/api/chat/sessions/{id}` | GET | Get session with messages |
| `/api/chat/sessions/{id}/messages` | POST | Append message to session |

---

## 3. AUTONOMY LEVELS

### Level 1: Conversational ✅ COMPLETE
Basic chat-driven interface with session logging and error handling.

### Level 2: Reasoners ✅ COMPLETE
Multi-turn memory, chain-of-thought reasoning, structured JSON outputs, source citations.

### Level 3: Agents ✅ MOSTLY COMPLETE
Goal/task acceptance, workflow planning, tool/API execution, approval gates, full audit trail.
**Gaps:** Long-term agent memory not standardized, error recovery not uniform, no full RBAC.

### Level 4: Innovators ⚠️ IN PROGRESS
Proactive scanning and task generation working (hourly cycle). Some experimentation harness exists.
**Gaps:** No hypothesis tracking, no closed-loop self-improvement, no rollback, no impact simulation.

### Level 5: Organizations ❌ TARGET
Full multi-agent orchestration with goal decomposition, resource allocation, cross-team conflict management, org-wide memory, advanced access control, automated escalation, and executive reporting.

**L5 Vision — What "Done" Looks Like:**
- JUGGERNAUT receives a high-level objective (e.g., "build a customer portal")
- ORCHESTRATOR decomposes it into atomic subtasks with dependency ordering
- Workers claim and execute tasks autonomously using real tools (GitHub PRs, deployments, DB migrations)
- VERCHAIN verification pipeline validates each completion (code review → tests → deploy → monitor)
- Failed tasks auto-retry with different strategies or escalate with full context
- System learns from outcomes: successful patterns get reinforced, failure patterns get flagged
- Zero human intervention for standard workflows; humans approve only novel/high-risk decisions

---

## 4. CURRENT STATE (2026-02-07)

### What's Working
- All 5 workers alive with active heartbeats (12-40s intervals)
- Proactive task generation running on 2-hour cycle
- Analysis tasks return real SQL-backed metrics
- Zero errors in recent execution logs
- Infrastructure healthy across all Railway services

### What's Broken — The Hamster Wheel
**Critical Issue:** AIHandler produces fake completions. Workers claim tasks, ask an LLM "what would you do?", save the text response as evidence, and mark done. No real work happens.

Evidence: Same 3 tasks repeat every 2 hours with identical fake results:
| Task | "Evidence" | Reality |
|------|-----------|---------|
| "Research: Domain flip opportunities" | `{"executed": true, "scan_type": "domain"}` | Doesn't scan anything. Writes a stub JSON. |
| "Review: Add tests for high-risk paths" | Returns generic worker stats | Doesn't add any tests. |
| "Report: Weekly ops snapshot" | Returns worker stats | Same output as every other analysis task. |

**953 "completed" tasks = 953 fake completions with zero actual work product.**

### Root Cause
AIHandler (`core/ai_handler.py`) lacks a tool executor. When a task requires real action (create a PR, run tests, deploy code), AIHandler calls an LLM for a text description of what it would do, then saves that description as "completion evidence." There is no `core/tool_executor.py` that actually invokes MCP tools.

---

## 5. REMEDIATION PLAN

### Priority 1: H-01 — AIHandler Real Execution (CRITICAL BLOCKER)
Build `core/tool_executor.py` that bridges AIHandler to the MCP server's 68+ tools. When a task requires action, the executor actually performs it (creates branches, writes code, runs queries) instead of asking an LLM to describe what it would do.

### Priority 2: H-02 — Budget & Cost Tracking
Implement per-task token/cost tracking with configurable limits. Prevent runaway LLM spend.

### Priority 3: H-03 — Credential Management
Store API keys in Railway env vars, not hardcoded. Add scoped access per worker type.

### Priority 4: H-04 — SQL Injection Prevention
Replace all string-interpolated SQL with parameterized queries throughout the codebase.

### Priority 5: H-05 — AnalysisHandler Differentiation
Analysis tasks currently return identical worker stats regardless of the actual request. Make the handler read task requirements and generate task-specific analysis.

### Priority 6: H-06 — Escalation Timeout
Add timeout-based escalation so tasks stuck in approval queues auto-escalate after configurable delay.

### Additional Findings (from 2026-02-07 codebase audit)
- Dedup window (72h) not preventing repeating tasks — proactive scanner regenerates same tasks each cycle
- ORCHESTRATOR was dead for 4+ days before heartbeat fix deployed
- 5 critical bugs fixed in commit `f84ef37`: heartbeat registration, task assignment SQL, approval routing, completion evidence validation, error handling

---

## 6. DASHBOARD VISION
**Current State:** Text-heavy, basic cards
**Target State:** Factorio-style visual command center

### Design References
- https://dribbble.com/shots/25963620-Fuse-AI-Dashboard-Overview-Interface-AI
- https://dribbble.com/shots/25701810-Finance-AI-Dashboard-UI-Website-Design
- https://dribbble.com/shots/25955330-Logistic-Company-Dashboard
- https://dribbble.com/shots/19797577-Bandwidth-Management-dark-mode-Dashboard-concept-design
- https://stock.adobe.com/1406443445

### Factory Floor Requirements
1. **Worker Stations** — Physical locations on 2D floor plan (EXECUTOR, ORCHESTRATOR, ANALYST, STRATEGIST, WATCHDOG)
2. **Task Flow** — Objects moving on conveyor belts between stations
3. **Visual Claiming** — When worker claims task, item moves to that station
4. **Completion Flow** — Completed tasks flow to "done" area
5. **Failure Indication** — Stuck/failed tasks pile up and flash red
6. **Heartbeat Pulse** — Stations visually pulse when worker is alive
7. **Real-Time Data** — Pulls from `juggernaut-dashboard-api-production.up.railway.app/public/dashboard/*`

### Tech Stack
- PixiJS for smooth 2D animation
- React Flow for node-based visualization
- D3.js for data-driven graphics

---

## 7. KEY METRICS
| Metric | Current Value | Notes |
|--------|---------------|-------|
| Tasks "Completed" | 953 | All fake — AIHandler produces stub evidence |
| Tasks Failed | ~11 | Low because nothing real is attempted |
| Workers Active | 5/5 | All heartbeating |
| Error Rate | <1% | Misleadingly low — errors only happen on real execution attempts |
| Real Work Product | 0 | No actual PRs, deployments, or deliverables from autonomous workers |

---

## 8. CREDENTIALS & ENDPOINTS

### For Claude Ops Partner
```
# Database (Neon PostgreSQL)
HTTP_ENDPOINT: https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql

# GitHub
REPO: SpartanPlumbingJosh/juggernaut-autonomy

# Railway API
URL: https://backboard.railway.com/graphql/v2
PROJECT_ID: e785854e-d4d6-4975-a025-812b63fe8961
ENVIRONMENT_ID: 8bfa6a1a-92f4-4a42-bf51-194b1c844a76

# Service IDs
juggernaut-engine:        9b7370c6-7764-4eb6-a64c-75cce1d23e06
juggernaut-watchdog:      52eb8b9f-6920-4a49-8522-7bc4415076a7
juggernaut-mcp:           ff009b38-e969-4be7-9930-cd7700062be6
juggernaut-puppeteer:     fcf41c38-5cc1-46ac-82f2-cf078b839786
juggernaut-dashboard-api: 18cb0f88-242b-4212-82d2-070fb2f1f621

# Dashboard API Endpoints
GET /public/dashboard/stats
GET /public/dashboard/workers
GET /public/dashboard/tasks
GET /public/dashboard/logs
GET /public/dashboard/alerts
GET /public/dashboard/revenue/summary
```

### Redeploy Command (Railway GraphQL)
```bash
curl -X POST https://backboard.railway.com/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {RAILWAY_TOKEN}" \
  -d '{"query": "mutation { serviceInstanceRedeploy(serviceId: \"SERVICE_ID\", environmentId: \"8bfa6a1a-92f4-4a42-bf51-194b1c844a76\") }"}'
```

---

## 9. WORKING AGREEMENTS

### Claude Sessions
- **Ops Partner (Claude in claude.ai):** Monitors, deploys, verifies, diagnoses. Does NOT edit code.
- **Windsurf (Josh's IDE):** All code changes, PRs, git operations.
- **Any Claude:** Can read/update this document when making significant progress.

### Code Standards
- Type hints required
- Docstrings required
- Parameterized SQL (no string concatenation)
- Proper error handling with logging (not print statements)
- CodeRabbit approval required before merge

### Task Workflow
1. Claim from governance_tasks (atomic)
2. Implement following coding standards
3. Create feature branch
4. Submit PR with documentation
5. Wait for CodeRabbit approval
6. Squash merge
7. Mark complete with evidence

---

## 10. RECENT FIXES

| Date | Fix | Status |
|------|-----|--------|
| 2026-02-07 | **5 Critical Bug Fixes (commit f84ef37)** — ORCHESTRATOR heartbeat registration, task assignment SQL, approval routing, completion evidence validation, error handling | ✅ Deployed, ORCHESTRATOR alive after 4+ days dead |
| 2026-02-01 | **System State Query Bugs (PR #277)** — Fixed type casting errors in `_get_system_state()` | ✅ Deployed v1.3.2 |
| 2026-01-31 | **Brain API Auth Headers (PR #276)** — Added Bearer/x-api-key/x-internal-api-secret support | ✅ Deployed |
| 2026-01-26 | **Scheduler + Proactive Work Generation** — Fixed execution/rescheduling, handler wiring, dedupe, diagnostics | ✅ Verified hourly generation working |
| 2026-01-26 | **Factory Floor (PixiJS)** — Visualization integrated at `/factory-floor` with live data | ✅ Rendering verified |
| 2026-01-25 | **AnalysisHandler** — Analysis tasks now use real SQL queries | ✅ Verified with real DB metrics |

---

## CHANGELOG
| Date | Change | By |
|------|--------|-----|
| 2026-01-25 | Initial document creation | Claude (Ops) |
| 2026-01-25 | AnalysisHandler fix verified | Claude (Ops) |
| 2026-01-26 | Factory Floor + scheduler/proactive fixes | Windsurf |
| 2026-02-01 | PR #276, #277 + metrics update | Claude (Ops) |
| 2026-02-07 | **Major rewrite** — Stripped Spartan Plumbing references, reframed as general-purpose platform, added L5 vision, documented hamster wheel problem, added remediation plan (H-01 through H-06), updated metrics to current state (953 tasks, all fake), added codebase audit findings | Claude (Ops) |
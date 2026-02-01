# JUGGERNAUT - Master Reference Document

> **Last Updated:** 2026-02-01
> **Purpose:** Single source of truth for all Claude sessions working on JUGGERNAUT
> **Update Instructions:** Any Claude session that makes significant progress should update this file and push to the repo

---

## 1. WHAT IS JUGGERNAUT

JUGGERNAUT is an autonomous AI business system targeting **$100M revenue** through self-operating task management and revenue generation. It progresses through five autonomy levels (L1-L5), from basic conversational interfaces to full organizational orchestration.

**Owner:** Josh Ferguson  
**Primary Business:** Spartan Plumbing (used as both automation target and development testbed)  
**Repository:** `SpartanPlumbingJosh/juggernaut-autonomy`

---

## 2. SYSTEM ARCHITECTURE

### Core Services (Railway)
| Service | ID | URL | Purpose |
|---------|-----|-----|---------|
| juggernaut-engine | `9b7370c6-7764-4eb6-a64c-75cce1d23e06` | juggernaut-engine-production.up.railway.app | Main autonomy loop |
| juggernaut-mcp | `ff009b38-e969-4be7-9930-cd7700062be6` | juggernaut-mcp-production.up.railway.app | MCP tools server |
| juggernaut-watchdog | `52eb8b9f-6920-4a49-8522-7bc4415076a7` | — | Health monitoring |
| juggernaut-puppeteer | `fcf41c38-5cc1-46ac-82f2-cf078b839786` | — | Browser automation |
| juggernaut-dashboard-api | `18cb0f88-242b-4212-82d2-070fb2f1f621` | juggernaut-dashboard-api-production.up.railway.app | Dashboard data API |

### Database (Neon PostgreSQL)
- **HTTP Endpoint:** `https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql`
- **Tables:** 69+ including `governance_tasks`, `execution_logs`, `worker_registry`, `experiments`

### Dashboard (Vercel)
- **Project:** spartan-hq
- **URL:** hq.spartan-plumbing.com
- **Status:** Factory Floor visualization live but still being tuned (layout + polish)

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

**Capabilities:**
- **Real-time Data Access**: Queries live database for task counts, worker status, revenue metrics
- **Tool Execution**: Can execute 68+ MCP tools including:
  - `sql_query` - Database queries
  - `github_*` - Repository operations (create branches, PRs, files)
  - `railway_*` - Infrastructure management (deployments, logs)
  - `war_room_*` - Slack communication
  - `hq_execute` - Governance task creation
- **Governance Task Fallback**: Creates follow-up tasks when tool execution fails
- **Session Persistence**: Maintains conversation history across sessions

**Architecture:**
```
User → spartan-hq frontend → Brain API → OpenRouter (function calling)
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

**Response Format:**
```json
{
  "response": "string",
  "session_id": "uuid",
  "tool_executions": [
    {"tool": "sql_query", "success": true, "arguments": {...}, "result": {...}}
  ],
  "iterations": 2,
  "input_tokens": 1500,
  "output_tokens": 500
}
```

---

## 3. AUTONOMY LEVELS - CURRENT STATUS

### Level 1: Conversational ✅ COMPLETE
| Requirement | Status | Notes |
|-------------|--------|-------|
| Conversational Interface | ✅ | Chat-driven via tasks/handlers |
| Short-Term Context | ✅ | In-session context |
| Basic Q&A | ✅ | |
| Session Logging | ✅ | execution_logs + task evidence |
| Simple Error Handling | ✅ | Partial - not uniform across all integrations |

### Level 2: Reasoners ✅ COMPLETE
| Requirement | Status | Notes |
|-------------|--------|-------|
| Multi-Turn Memory | ✅ | Within task/workflow |
| Chain-of-Thought Reasoning | ✅ | Planning + multi-step execution |
| Suggests Actions | ✅ | |
| References & Sourcing | ✅ | Research tasks cite sources; analysis now includes sql_used |
| Uncertainty/Risk Warnings | ⚠️ Partial | |
| Structured Outputs | ✅ | JSON evidence patterns |

### Level 3: Agents ✅ MOSTLY COMPLETE
| Requirement | Status | Notes |
|-------------|--------|-------|
| Goal/Task Acceptance | ✅ | governance_tasks + workflows |
| Workflow Planning | ✅ | Multi-step orchestration |
| Tool/API Execution | ✅ | DB, GitHub, web fetch, etc. |
| Persistent Task Memory | ⚠️ Partial | Task state persists; long-term agent memory not standardized |
| Error Recovery | ⚠️ Partial | Some retry/fallback; not uniform |
| Dry-Run Mode | ⚠️ Partial | Concept exists; not integrated everywhere |
| Human-in-the-Loop | ✅ | Approval gates exist |
| Action Logging | ✅ | Full audit trail |
| Permission/Scope Control | ⚠️ Partial | Some guardrails; no full RBAC |

### Level 4: Innovators ⚠️ IN PROGRESS
| Requirement | Status | Notes |
|-------------|--------|-------|
| Proactive Scanning | ⚠️ Partial | Scan concepts exist; not always-on with auto-task creation |
| Experimentation | ⚠️ Partial | Some harness exists; no formal lifecycle |
| Hypothesis Tracking | ❌ | Not implemented |
| Self-Improvement | ❌ | No closed-loop policy changes |
| Sandboxed Innovation | ⚠️ Partial | Needs explicit boundaries |
| Rollback | ❌ | Requires transactionality |
| Proposes New Automations | ⚠️ Partial | Suggestions exist; no approval workflow |
| Impact Simulation | ❌ | Beyond basic dry-run |

### Level 5: Organizations ❌ NOT YET
| Requirement | Status | Notes |
|-------------|--------|-------|
| Goal Decomposition | ⚠️ Partial | Some exists; not org-wide |
| Multi-Agent Orchestration | ⚠️ Partial | Workers exist; cross-dept is aspirational |
| Resource Allocation | ⚠️ Partial | Basic scheduling; no budget optimization |
| Cross-Team Conflict Mgmt | ❌ | |
| Org-Wide Memory | ❌ | Needs durable knowledge base |
| Advanced Access Control | ❌ | Needs RBAC + audit |
| Automated Escalation | ⚠️ Partial | Some gates; escalation logic incomplete |
| Resilience/Failover | ⚠️ Partial | Basic retries; no full HA |
| Executive Reporting | ⚠️ Partial | Dashboards exist; traceability improving |

---

## 4. CURRENT PRIORITIES

### Immediate (This Week)
| Priority | Description | Owner | Status |
|----------|-------------|-------|--------|
| 1 | **Factory Floor Dashboard** - Visual command center (Factorio-style) | Windsurf | 🔄 In Progress (live; layout + polish ongoing) |
| 2 | **Proactive Work Generation** - System creates its own tasks | Windsurf | ✅ Working (hourly generation + diagnostics) |
| 3 | **Slack Notifications** - Alerts for completions/failures | Windsurf | Not Started |

### Short-Term (Next 2-4 Weeks)
| Priority | Description | Status |
|----------|-------------|--------|
| 4 | Verification for all action types (deploys, DB writes) | Not Started |
| 5 | RBAC + scoped credentials per tool | Not Started |
| 6 | Formal experiment lifecycle (hypothesis → test → measure → rollback) | Not Started |

### Medium-Term (L5 Target)
- Org-wide memory store (auditable, permissioned, long-retention)
- Cross-team conflict management
- Full resilience/failover strategy
- Multi-tenant support

---

## 5. RECENT FIXES (Verified Working)
| Date | Fix | Verification |
|------|-----|--------------|
| 2026-01-25 | **AnalysisHandler** - Analysis tasks now use real SQL queries instead of AIHandler hallucinations | ✅ Task `b8d9f44c` completed with real metrics (97.4% success rate from actual DB) |
| 2026-01-25 | **PR Evidence Classification** - PRs correctly classified as `pr_created` until GitHub API confirms merge | Implemented; awaiting end-to-end test with code task |
| 2026-01-26 | **Factory Floor (spartan-hq)** - PixiJS visualization integrated at `/factory-floor` with live data polling | Rendering verified; ongoing layout tuning |
| 2026-01-26 | **Queue API mismatch (spartan-hq)** - `/api/dashboard/queue` now derives queue from `/public/dashboard/tasks?status=approved` | Fix merged locally; requires deploy to verify |
| 2026-01-26 | **Worker status mapping (spartan-hq)** - Treat `status: active` as ONLINE; heartbeat optional | Fix merged locally; requires deploy to verify |
| 2026-01-26 | **Pixi cleanup hardening (spartan-hq)** - stop ticker, clear stage, defensive destroy | Fix merged locally; reduces unmount crash risk |
| 2026-01-26 | **Scheduler + proactive work generation** - Fixed scheduled execution/rescheduling, proactive_diverse handler wiring, dedupe (completed tasks no longer block), and added detailed diagnostics logging | Verified: Proactive generation working hourly; EXECUTOR claiming/completing; queue caught up |
| 2026-01-31 | **Brain API Auth Headers (PR #276)** - Added support for `Authorization: Bearer` header, `x-api-key`, and `x-internal-api-secret` headers in addition to query parameter auth | ✅ Deployed and verified - Neural Chat now accepts auth via headers from frontend proxy |
| 2026-02-01 | **System State Query Bugs (PR #277)** - Fixed `_get_system_state()` type casting errors: task counts returned as strings, heartbeat EXTRACT(EPOCH) parsing, and revenue query column mismatch | ✅ Deployed v1.3.2 - No more warnings in logs, system state endpoint working correctly |

---

## 6. DASHBOARD VISION
**Current State:** Text-heavy, basic cards, "dopey as fuck"

**Target State:** Factorio-style visual command center

### Design References
- https://dribbble.com/shots/25963620-Fuse-AI-Dashboard-Overview-Interface-AI
- https://dribbble.com/shots/25701810-Finance-AI-Dashboard-UI-Website-Design
- https://dribbble.com/shots/25955330-Logistic-Company-Dashboard
- https://dribbble.com/shots/19797577-Bandwidth-Management-dark-mode-Dashboard-concept-design
- https://stock.adobe.com/1406443445

### Factory Floor Requirements
1. **Worker Stations** - Physical locations on 2D floor plan (EXECUTOR, ORCHESTRATOR, ANALYST, STRATEGIST, WATCHDOG)
2. **Task Flow** - Objects moving on conveyor belts between stations
3. **Visual Claiming** - When worker claims task, item moves to that station
4. **Completion Flow** - Completed tasks flow to "done" area
5. **Failure Indication** - Stuck/failed tasks pile up and flash red
6. **Heartbeat Pulse** - Stations visually pulse when worker is alive
7. **Real-Time Data** - Pulls from `juggernaut-dashboard-api-production.up.railway.app/public/dashboard/*`

### Tech Recommendations
- PixiJS for smooth 2D animation
- React Flow for node-based visualization
- D3.js for data-driven graphics

---

## 7. KEY METRICS
| Metric | Current Value | Target |
|--------|---------------|--------|
| Tasks Completed | 665 | — |
| Tasks Failed | 11 | <5% failure rate |
| Revenue | $0 | $100M |
| Workers Active | 5/5 | 100% uptime |
| Error Rate | 1.65% | <5% ✅ |

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

## 10. OPEN QUESTIONS
- [ ] Resume Domain Flip experiment? (Requires ~$20 approval for domain purchase)
- [ ] ServiceTitan integration for revenue tracking?
- [ ] Voice interface (SARAH) priority?

---

## CHANGELOG
| Date | Change | By |
|------|--------|-----|
| 2026-01-25 | Initial document creation | Claude (Ops) |
| 2026-01-25 | AnalysisHandler fix verified | Claude (Ops) |
| 2026-01-26 | Added Factory Floor dashboard progress + spartan-hq fixes (queue, worker status, Pixi cleanup) | Windsurf |
| 2026-01-26 | Added scheduler/proactive generation fixes status (ON CONFLICT fixes, rescheduling, proactive_diverse wiring, dedupe + diagnostics logging) + current state snapshot | Windsurf |
| 2026-02-01 | Added PR #276 (Brain API auth headers) and PR #277 (system state query fixes) + updated metrics (665 completed, 1.65% error rate) | Claude (Ops) |

# JUGGERNAUT Database Schema

Last updated: 2026-01-18

## Overview

21 tables across 4 categories:
- **Core Operations**: Worker management, tasks, goals, approvals
- **Revenue Pipeline**: Opportunities, revenue events, scoring
- **Learning & Memory**: Learnings, memories, logic evolution
- **Logging & Metrics**: Execution logs, worker metrics, communications

---

## CORE OPERATIONS

### worker_registry
Registered workers/agents in the system.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| worker_id | varchar | Unique identifier (e.g., 'ORCHESTRATOR', 'SARAH') |
| name | varchar | Display name |
| description | text | What this worker does |
| level | autonomy_level | L1-L5 autonomy level |
| status | worker_status | offline/active/busy/error |
| capabilities | jsonb | List of capability strings |
| permissions | jsonb | Permission configuration |
| forbidden_actions | jsonb | Actions this worker cannot perform |
| approval_required_for | jsonb | Actions requiring human approval |
| max_concurrent_tasks | int | Task concurrency limit |
| max_cost_per_task_cents | int | Cost limit per task |
| max_cost_per_day_cents | int | Daily cost limit |
| health_score | numeric | 0.0-1.0 health indicator |
| last_heartbeat | timestamptz | Last activity timestamp |

### goals
High-level objectives assigned to workers.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| parent_goal_id | uuid | Parent goal for decomposition |
| title | varchar | Goal title |
| description | text | Detailed description |
| success_criteria | jsonb | Measurable success conditions |
| created_by | varchar | Who created this goal |
| assigned_worker_id | uuid | Worker assigned to this goal |
| status | varchar | active/completed/failed/paused |
| progress | numeric | 0-100 completion percentage |
| deadline | timestamptz | Target completion date |
| max_cost_cents | int | Budget for this goal |
| outcome | text | Final outcome description |

### governance_tasks
Discrete tasks assigned to workers.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| goal_id | uuid | Parent goal |
| parent_task_id | uuid | Parent task for subtasks |
| assigned_worker | varchar | Worker ID |
| task_type | varchar | Task classification |
| title | varchar | Task title |
| payload | jsonb | Task parameters |
| priority | task_priority | critical/high/normal/low/deferred |
| result | jsonb | Task output |
| error_message | text | Error if failed |
| depends_on | jsonb | Task dependencies |
| attempt_count | int | Retry attempts |
| requires_approval | bool | Needs human approval |
| estimated_cost_cents | int | Expected cost |
| actual_cost_cents | int | Actual cost incurred |

### approvals
Human-in-the-loop approval requests.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| task_id | uuid | Related task |
| goal_id | uuid | Related goal |
| worker_id | varchar | Requesting worker |
| action_type | varchar | Type of action |
| action_description | text | What needs approval |
| action_data | jsonb | Action parameters |
| risk_level | varchar | low/medium/high/critical |
| decision | approval_decision | pending/approved/rejected |
| decided_by | varchar | Who decided |
| expires_at | timestamptz | Approval deadline |

---

## REVENUE PIPELINE

### opportunities
Revenue opportunities in the pipeline.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| source_id | uuid | Origin source |
| opportunity_type | varchar | domain/saas/digital_product/api_service |
| category | varchar | Category within type |
| estimated_value | numeric | Expected revenue |
| confidence_score | numeric | 0.0-1.0 success probability |
| status | varchar | new/qualified/contacted/quoted/won/lost |
| stage | varchar | Pipeline stage |
| customer_name | varchar | Lead/customer name |
| customer_contact | jsonb | Contact information |
| description | text | Opportunity details |
| metadata | jsonb | Additional data |
| assigned_to | varchar | Worker pursuing this |
| created_by | varchar | Who identified this |
| identified_at | timestamptz | When identified |
| closed_at | timestamptz | When closed |
| expires_at | timestamptz | Opportunity expiration |

### opportunity_sources
Sources that generate opportunities.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| name | varchar | Source name |
| source_type | varchar | Type (scanner/api/manual) |
| config | jsonb | Source configuration |
| active | bool | Is source active |

### revenue_events
Actual revenue transactions.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| opportunity_id | uuid | Related opportunity |
| event_type | varchar | sale/refund/recurring |
| revenue_type | varchar | one_time/recurring/usage |
| gross_amount | numeric | Gross revenue |
| net_amount | numeric | After fees/costs |
| currency | varchar | Currency code |
| source | varchar | Revenue source |
| attribution | jsonb | Attribution details |
| occurred_at | timestamptz | When transaction occurred |

### revenue_summary
Aggregated revenue metrics by period.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| period_type | varchar | daily/weekly/monthly |
| period_start | date | Period start |
| period_end | date | Period end |
| gross_revenue | numeric | Total gross |
| net_revenue | numeric | Total net |
| opportunity_count | int | Opportunities in period |
| won_count | int | Won opportunities |
| conversion_rate | numeric | Win rate |
| avg_deal_size | numeric | Average deal |
| pipeline_value | numeric | Pipeline total |

### scoring_models
ML models for opportunity scoring.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| name | varchar | Model name |
| version | int | Model version |
| active | bool | Is model in use |
| model_type | varchar | Model type |
| config | jsonb | Model configuration |
| accuracy | numeric | Model accuracy |

---

## LEARNING & MEMORY

### learnings
Extracted insights from operations.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| worker_id | varchar | Learning worker |
| category | varchar | Learning category |
| summary | text | Learning summary |
| details | jsonb | Detailed information |
| confidence | numeric | Confidence level |
| applied_count | int | Times applied |
| effectiveness_score | numeric | How effective |
| is_validated | bool | Human validated |

### memories
Persistent memory storage.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| scope | varchar | global/worker/goal |
| scope_id | varchar | Scope identifier |
| key | varchar | Memory key |
| content | text | Memory content |
| memory_type | varchar | fact/preference/context |
| importance | numeric | 0.0-1.0 importance |
| access_count | int | Access frequency |
| expires_at | timestamptz | Memory expiration |

### logic_evolution
System learning and insights.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| category | varchar | bug/decision/pattern/gotcha |
| component | varchar | System component |
| insight | text | The insight |
| context | text | Additional context |
| importance | numeric | 0.0-1.0 importance |
| source | varchar | Source instance |

---

## LOGGING & METRICS

### execution_logs
All system actions and events.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| goal_id | uuid | Related goal |
| task_id | uuid | Related task |
| worker_id | varchar | Acting worker |
| level | log_level | debug/info/warn/error/critical |
| action | varchar | Action type |
| message | text | Log message |
| input_data | jsonb | Action input |
| output_data | jsonb | Action output |
| error_data | jsonb | Error details |
| duration_ms | int | Action duration |
| tokens_used | int | AI tokens |
| cost_cents | int | Action cost |
| source | varchar | Log source |

### worker_metrics
Aggregated worker performance.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| worker_id | varchar | Worker |
| period_start | timestamptz | Period start |
| period_end | timestamptz | Period end |
| tasks_assigned | int | Tasks received |
| tasks_completed | int | Tasks done |
| tasks_failed | int | Tasks failed |
| avg_completion_time_ms | int | Average time |
| total_cost_cents | int | Total cost |
| total_tokens_used | int | Total tokens |

### communications
Inter-worker messages.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| from_worker | varchar | Sender |
| to_worker | varchar | Recipient |
| message_type | varchar | Message type |
| subject | varchar | Subject |
| content | jsonb | Message content |
| status | varchar | sent/read/responded |

### capabilities
Available system capabilities.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| name | varchar | Capability name |
| category | varchar | Category |
| implementation_type | varchar | How implemented |
| implementation_config | jsonb | Config |
| cost_per_use_cents | int | Usage cost |
| is_active | bool | Is available |

---

## VIEWS

### v_active_pipeline
Active opportunities with source info.

### v_pending_approvals
Approvals awaiting decision with task/goal context.

### v_revenue_by_source
Revenue aggregated by source.

---

## ENUMS

### autonomy_level
L1, L2, L3, L4, L5

### worker_status
offline, active, busy, error, maintenance

### task_priority
critical, high, normal, low, deferred

### log_level
debug, info, warn, error, critical

### approval_decision
pending, approved, rejected, expired

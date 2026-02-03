# Milestone 6: OpenRouter Smart Routing - Architecture

## Goal
Intelligent model selection based on task requirements, cost optimization, and performance tracking. Route each task to the most appropriate model while staying within budget constraints.

## Core Concept
Different tasks need different models. Simple tasks use cheap models, complex tasks use expensive smart models. The system automatically selects the best model for each task type while tracking costs and performance.

## Components

### 1. Routing Policies (`core/routing_policies.py`)
**Purpose:** Define rules for model selection based on task characteristics

**Policy Types:**
- **Normal:** Balanced cost/performance (GPT-4o-mini, Claude Sonnet)
- **Deep Research:** Maximum intelligence (GPT-4o, Claude Opus)
- **Code:** Specialized for coding (GPT-4o, Claude Sonnet)
- **Ops:** Ultra-cheap for simple tasks (GPT-3.5, Claude Haiku)

**Policy Structure:**
```python
{
    "name": "normal",
    "description": "Balanced cost and performance",
    "models": [
        {"provider": "openai", "model": "gpt-4o-mini", "priority": 1},
        {"provider": "anthropic", "model": "claude-3-5-sonnet", "priority": 2}
    ],
    "max_cost_per_task": 0.10,
    "max_tokens": 4000,
    "temperature": 0.7
}
```

### 2. Model Selector (`core/model_selector.py`)
**Purpose:** Select the best model for a given task

**Selection Algorithm:**
1. Determine task type and complexity
2. Get applicable routing policy
3. Check model availability and rate limits
4. Consider recent performance metrics
5. Select highest priority available model
6. Track selection for cost monitoring

**Task Type Mapping:**
- `investigate_error` → Code policy
- `deploy_code` → Code policy
- `analyze_logs` → Normal policy
- `fix_bug` → Code policy
- `simple_query` → Ops policy

### 3. Cost Tracker (`core/cost_tracker.py`)
**Purpose:** Monitor and enforce budget constraints

**Tracking Metrics:**
- Cost per task
- Cost per model
- Cost per policy
- Daily/weekly/monthly totals
- Cost per worker

**Budget Enforcement:**
- Daily budget limit
- Per-task budget limit
- Alert when approaching limits
- Pause expensive models when over budget

### 4. Performance Tracker (`core/performance_tracker.py`)
**Purpose:** Track model performance for optimization

**Metrics:**
- Success rate per model
- Average response time
- Token usage efficiency
- Error rates
- User satisfaction (if available)

**Optimization:**
- Demote underperforming models
- Promote high-performing models
- Adjust priorities based on metrics

### 5. OpenRouter Client (`core/openrouter_client.py`)
**Purpose:** Unified interface to OpenRouter API

**Features:**
- Single API for multiple providers
- Automatic failover
- Rate limit handling
- Cost tracking
- Response streaming

## Database Schema

### `routing_policies` Table
```sql
CREATE TABLE routing_policies (
    id UUID PRIMARY KEY,
    name VARCHAR(50) UNIQUE,
    description TEXT,
    policy_config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### `model_selections` Table
```sql
CREATE TABLE model_selections (
    id UUID PRIMARY KEY,
    task_id UUID REFERENCES governance_tasks(id),
    policy_name VARCHAR(50),
    selected_model VARCHAR(100),
    selected_provider VARCHAR(50),
    estimated_cost DECIMAL(10,4),
    actual_cost DECIMAL(10,4),
    tokens_used INTEGER,
    response_time_ms INTEGER,
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `model_performance` Table
```sql
CREATE TABLE model_performance (
    id UUID PRIMARY KEY,
    model_name VARCHAR(100),
    provider VARCHAR(50),
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    total_requests INTEGER,
    successful_requests INTEGER,
    failed_requests INTEGER,
    avg_response_time_ms INTEGER,
    total_cost DECIMAL(10,2),
    avg_tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `cost_budgets` Table
```sql
CREATE TABLE cost_budgets (
    id UUID PRIMARY KEY,
    budget_type VARCHAR(50),
    budget_period VARCHAR(20),
    budget_amount DECIMAL(10,2),
    spent_amount DECIMAL(10,2) DEFAULT 0,
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    alert_threshold DECIMAL(5,2) DEFAULT 0.80,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

### Backend (`juggernaut-autonomy`)
- `GET /api/routing/policies` - Get routing policies
- `POST /api/routing/policies` - Create/update policy
- `GET /api/routing/costs` - Get cost statistics
- `GET /api/routing/performance` - Get model performance
- `POST /api/routing/select` - Select model for task

## Routing Decision Flow

```
1. Task arrives
   ↓
2. Determine task type and complexity
   ↓
3. Get applicable routing policy
   ↓
4. Check budget constraints
   ↓
5. Get available models from policy
   ↓
6. Check model performance metrics
   ↓
7. Select highest priority available model
   ↓
8. Track selection and estimated cost
   ↓
9. Execute task with selected model
   ↓
10. Track actual cost and performance
   ↓
11. Update performance metrics
```

## Default Routing Policies

### Normal (Balanced)
- **Models:** GPT-4o-mini (primary), Claude Sonnet (fallback)
- **Max Cost:** $0.10 per task
- **Use Case:** General tasks, analysis, investigation

### Deep Research (Maximum Intelligence)
- **Models:** GPT-4o (primary), Claude Opus (fallback)
- **Max Cost:** $1.00 per task
- **Use Case:** Complex analysis, strategic decisions

### Code (Specialized)
- **Models:** GPT-4o (primary), Claude Sonnet (fallback)
- **Max Cost:** $0.50 per task
- **Use Case:** Code analysis, debugging, fixes

### Ops (Ultra-Cheap)
- **Models:** GPT-3.5-turbo (primary), Claude Haiku (fallback)
- **Max Cost:** $0.01 per task
- **Use Case:** Simple queries, status checks, formatting

## Cost Optimization Strategies

### 1. Automatic Downgrade
- If expensive model fails → try cheaper model
- If task is simpler than expected → use cheaper model

### 2. Batch Processing
- Group similar tasks
- Use same model for batch
- Reduce context switching

### 3. Caching
- Cache common responses
- Reuse analysis results
- Avoid redundant API calls

### 4. Budget Enforcement
- Pause expensive models when over budget
- Alert humans when approaching limits
- Automatic failover to cheaper models

## Success Metrics

1. **Cost Efficiency:** Average cost per task < $0.05
2. **Performance:** 95%+ success rate across all models
3. **Response Time:** < 5 seconds average
4. **Budget Compliance:** Stay within daily/weekly budgets
5. **Model Utilization:** Balanced usage across policies

## Integration with Previous Milestones

**M1 (Chat Control Plane):**
- Show selected model in real-time
- Display cost per message

**M2 (Self-Heal):**
- Use Ops policy for simple health checks
- Use Code policy for repairs

**M3 (Logs Crawler):**
- Use Normal policy for error analysis
- Use Code policy for investigation tasks

**M4 (Code Crawler):**
- Use Code policy for analysis
- Use Normal policy for reporting

**M5 (Engine Autonomy):**
- Engine selects model per task
- Tracks costs per worker
- Enforces budgets

## The Complete L5 System

```
1. Logs Crawler detects error (M3)
   ↓
2. Creates investigation task
   ↓
3. Engine routes to capable worker (M5)
   ↓
4. Smart Routing selects best model (M6) ⭐
   ↓
5. Worker analyzes with selected model
   ↓
6. Code Crawler validates fix (M4)
   ↓
7. Engine assigns deployment task (M5)
   ↓
8. Smart Routing selects deployment model (M6) ⭐
   ↓
9. Human approves
   ↓
10. Worker deploys
   ↓
11. Self-Heal verifies (M2)
   ↓
12. Loop continues with optimized costs ⭐
```

This is 100% L5 autonomy - intelligent, cost-optimized, self-healing autonomous operation.

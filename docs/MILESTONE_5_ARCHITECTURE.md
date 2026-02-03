# Milestone 5: Engine Autonomy Restoration - Architecture

## Goal
True autonomous operation. The engine continuously executes tasks, routes work to capable workers, handles failures gracefully, and operates 24/7 with minimal human intervention.

## Core Concept
The autonomy loop becomes self-healing and self-routing. Tasks flow automatically from creation → assignment → execution → completion, with the system detecting and recovering from failures without human intervention.

## Components

### 1. Task Router (`core/task_router.py`)
**Purpose:** Intelligently route tasks to appropriate workers

**Routing Strategy:**
1. Analyze task requirements (type, priority, capabilities needed)
2. Find available workers with matching capabilities
3. Consider worker load and success rates
4. Assign task to best-fit worker
5. Track assignment and monitor progress

**Routing Rules:**
- `investigate_error` → Worker with code analysis capability
- `deploy_code` → Worker with deployment capability
- `analyze_logs` → Worker with log analysis capability
- `generic` → Any available worker

### 2. Worker Capability Matcher (`core/worker_matcher.py`)
**Purpose:** Match tasks to workers based on capabilities

**Capability System:**
- Each worker declares capabilities: `['code_analysis', 'deployment', 'log_analysis']`
- Each task declares required capabilities
- Matcher finds workers with ALL required capabilities
- Considers worker availability and recent success rate

**Worker States:**
- `idle` - Available for work
- `busy` - Currently executing a task
- `offline` - Not responding to heartbeats
- `failed` - Recent failures, needs investigation

### 3. Autonomous Execution Loop (`core/autonomy_loop.py`)
**Purpose:** Continuously execute tasks without human intervention

**Loop Flow:**
```python
while True:
    # 1. Check for pending tasks
    pending_tasks = get_pending_tasks(limit=10)
    
    # 2. Route each task
    for task in pending_tasks:
        worker = router.find_best_worker(task)
        if worker:
            assign_task(task, worker)
    
    # 3. Check for stuck tasks
    stuck_tasks = get_stuck_tasks()
    for task in stuck_tasks:
        recovery.handle_stuck_task(task)
    
    # 4. Update worker heartbeats
    update_worker_status()
    
    # 5. Sleep for interval
    sleep(30)  # 30 seconds
```

### 4. Retry Strategy Engine (`core/retry_strategy.py`)
**Purpose:** Intelligent retry logic for failed tasks

**Retry Policies:**
1. **Transient Failure** (network timeout, rate limit)
   - Retry immediately with exponential backoff
   - Max 3 retries

2. **Worker Failure** (worker crashed, timeout)
   - Reassign to different worker
   - Max 2 reassignments

3. **Task Failure** (code error, invalid input)
   - Move to `waiting_approval` for human review
   - Create investigation task

4. **Persistent Failure** (fails 3+ times)
   - Mark as `blocked`
   - Create high-priority investigation task
   - Alert humans

### 5. Recovery Manager (`core/recovery_manager.py`)
**Purpose:** Detect and recover from various failure modes

**Recovery Actions:**
- **Stuck Task:** Reset to pending, reassign to different worker
- **Dead Worker:** Mark offline, reassign all tasks
- **Infinite Loop:** Detect repeated failures, move to waiting_approval
- **Resource Exhaustion:** Pause new assignments, wait for completion
- **Database Errors:** Retry with backoff, alert if persistent

### 6. Task Dependency Resolver (`core/task_dependencies.py`)
**Purpose:** Handle tasks that depend on other tasks

**Dependency Rules:**
- Task B depends on Task A → B can't start until A completes
- If A fails → B moves to blocked
- If A succeeds → B moves to pending
- Circular dependencies → Detected and rejected

### 7. Worker Health Monitor (`core/worker_health.py`)
**Purpose:** Track worker health and performance

**Health Metrics:**
- Heartbeat freshness (< 5 minutes = healthy)
- Success rate (last 10 tasks)
- Average execution time
- Error patterns
- Resource usage (if available)

**Health Actions:**
- Healthy → Assign new tasks
- Degraded → Reduce task assignments
- Unhealthy → Stop assignments, investigate
- Offline → Mark offline, reassign tasks

## Database Schema

### `task_assignments` Table
```sql
CREATE TABLE task_assignments (
    id UUID PRIMARY KEY,
    task_id UUID REFERENCES governance_tasks(id),
    worker_id UUID REFERENCES workers(id),
    assigned_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50),
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `worker_capabilities` Table
```sql
CREATE TABLE worker_capabilities (
    id UUID PRIMARY KEY,
    worker_id UUID REFERENCES workers(id),
    capability VARCHAR(100),
    proficiency INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(worker_id, capability)
);
```

### `task_dependencies` Table
```sql
CREATE TABLE task_dependencies (
    id UUID PRIMARY KEY,
    task_id UUID REFERENCES governance_tasks(id),
    depends_on_task_id UUID REFERENCES governance_tasks(id),
    dependency_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(task_id, depends_on_task_id)
);
```

### `autonomy_state` Table
```sql
CREATE TABLE autonomy_state (
    id UUID PRIMARY KEY,
    is_running BOOLEAN DEFAULT TRUE,
    last_loop_at TIMESTAMP,
    tasks_processed INTEGER DEFAULT 0,
    tasks_assigned INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    loop_duration_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### `retry_history` Table
```sql
CREATE TABLE retry_history (
    id UUID PRIMARY KEY,
    task_id UUID REFERENCES governance_tasks(id),
    retry_number INTEGER,
    retry_reason VARCHAR(200),
    previous_worker_id UUID,
    new_worker_id UUID,
    retry_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

### Backend (`juggernaut-autonomy`)
- `GET /api/engine/status` - Get autonomy loop status
- `POST /api/engine/start` - Start autonomy loop
- `POST /api/engine/stop` - Stop autonomy loop
- `GET /api/engine/assignments` - Get task assignments
- `GET /api/engine/workers` - Get worker status
- `POST /api/engine/reassign/{task_id}` - Manually reassign task

## Autonomy Loop States

### Running
- Continuously processing tasks
- Assigning to workers
- Monitoring progress
- Handling failures

### Paused
- Not assigning new tasks
- Existing tasks continue
- Monitoring only

### Stopped
- No task processing
- Manual intervention required
- Emergency stop state

## Safety Mechanisms

### 1. Circuit Breaker
- If error rate > 50% in last 10 tasks → Pause loop
- Alert humans
- Resume when errors drop below 20%

### 2. Rate Limiting
- Max 10 task assignments per minute
- Prevents overwhelming workers
- Prevents runaway execution

### 3. Budget Enforcement
- Each task has max execution time
- Budget exceeded → Task stopped
- Worker marked as potentially stuck

### 4. Human Approval Gates
- Risky tasks (deployment, deletion) → waiting_approval
- High-value tasks → waiting_approval
- Tasks that failed 3+ times → waiting_approval

## Success Metrics

1. **Autonomy Rate:** % of tasks completed without human intervention
2. **Assignment Speed:** Time from pending → assigned
3. **Success Rate:** % of tasks completed successfully
4. **Recovery Rate:** % of failures recovered automatically
5. **Uptime:** % of time loop is running

## Phase 1 (Tonight - 2 hours)
1. Database schema
2. Task router (basic)
3. Worker matcher
4. Autonomy loop (basic)

## Phase 2 (Next Session - 2 hours)
1. Retry strategy engine
2. Recovery manager
3. Worker health monitor

## Phase 3 (Next Session - 1 hour)
1. Engine Control UI
2. Testing
3. Deployment

## Integration with Previous Milestones

**M1 (Chat Control Plane):**
- Engine status visible in Control Plane
- Can stop/start engine from UI

**M2 (Self-Heal):**
- Self-heal can trigger engine restart
- Engine uses self-heal for recovery

**M3 (Logs Crawler):**
- Logs crawler creates tasks
- Engine executes investigation tasks

**M4 (Code Crawler):**
- Code crawler creates tasks
- Engine executes fix tasks

## The Complete L5 Loop

```
1. Logs Crawler detects error (M3)
   ↓
2. Creates investigation task
   ↓
3. Engine assigns to capable worker (M5)
   ↓
4. Worker analyzes code (M4)
   ↓
5. Worker creates fix PR
   ↓
6. Human approves PR
   ↓
7. Engine deploys fix
   ↓
8. Logs Crawler verifies fix
   ↓
9. Self-Heal resets any stuck tasks (M2)
   ↓
10. Loop continues 24/7
```

This is true L5 autonomy - the system finds work, does work, fixes itself, and only asks for help on risky decisions.

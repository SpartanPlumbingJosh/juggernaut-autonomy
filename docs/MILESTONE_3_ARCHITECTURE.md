# Milestone 3: Railway Logs Crawler - Architecture

## Goal
Stop manual log babysitting. Automatically detect errors in Railway logs, fingerprint them, and create governance tasks for investigation.

## Components

### 1. Railway API Client (`core/railway_client.py`)
**Purpose:** Fetch logs from Railway API

**Capabilities:**
- Authenticate with Railway API token
- Fetch logs for specific project/environment
- Filter by log level (error, warning, info)
- Paginate through large log volumes
- Handle rate limits gracefully

**API Endpoints:**
- `GET /projects/{projectId}/environments/{envId}/logs`
- Query params: `level`, `since`, `limit`

### 2. Error Fingerprinter (`core/error_fingerprinter.py`)
**Purpose:** Deduplicate errors by creating unique fingerprints

**Algorithm:**
1. Extract error message
2. Normalize (remove timestamps, IDs, specific values)
3. Extract stack trace signature
4. Create SHA256 hash of normalized error
5. Store fingerprint with first/last occurrence

**Example:**
```
Raw: "HTTP 500 at /api/foo user_id=123 timestamp=2024-01-01"
Normalized: "HTTP 500 at /api/foo user_id=* timestamp=*"
Fingerprint: "abc123def456..."
```

### 3. Log Crawler Scheduler (`core/log_crawler.py`)
**Purpose:** Run every 5 minutes, fetch new logs, fingerprint errors

**Flow:**
1. Fetch logs since last run (stored in `log_crawler_state`)
2. Parse each log line
3. Extract errors (level=ERROR or CRITICAL)
4. Fingerprint each error
5. Update occurrence counts
6. Trigger alerts if needed
7. Update last_run timestamp

**State Management:**
- Store last_run timestamp in database
- Track processed log IDs to avoid duplicates
- Handle restarts gracefully

### 4. Alert Rules Engine (`core/alert_rules.py`)
**Purpose:** Decide when to create governance tasks

**Rules:**
1. **New Fingerprint:** First time seeing this error → Create task
2. **Spike Detection:** Error rate > 10/min → Create task
3. **Sustained Errors:** Same error for 5+ minutes → Create task
4. **Critical Errors:** Any CRITICAL level → Create task immediately

**Cooldown:** 30 minutes between alerts for same fingerprint

### 5. Governance Task Creator (`core/task_creator.py`)
**Purpose:** Create well-formed governance tasks for errors

**Task Template:**
```
Title: "Investigate error: {error_summary}"
Description: 
  - Error fingerprint: {fingerprint}
  - First seen: {timestamp}
  - Occurrences: {count}
  - Last seen: {timestamp}
  - Example log: {sample}
  - Stack trace: {trace}
Priority: high (for new errors), medium (for recurring)
Type: investigate_error
Metadata: {fingerprint, occurrences, etc}
```

### 6. System Health UI (`spartan-hq/app/(app)/system-health/page.tsx`)
**Purpose:** Dashboard showing top errors and trends

**Features:**
- Top 10 error fingerprints by occurrence
- Error rate chart (last 24h)
- New errors today
- Resolved errors (no occurrences in 24h)
- Click error → See all occurrences
- Click "Create Task" → Manual task creation
- Auto-refresh every 30 seconds

## Database Schema

### `railway_logs` Table
```sql
CREATE TABLE railway_logs (
    id UUID PRIMARY KEY,
    project_id VARCHAR(100),
    environment_id VARCHAR(100),
    log_level VARCHAR(20),
    message TEXT,
    timestamp TIMESTAMP,
    raw_log JSONB,
    fingerprint VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `error_fingerprints` Table
```sql
CREATE TABLE error_fingerprints (
    id UUID PRIMARY KEY,
    fingerprint VARCHAR(64) UNIQUE,
    normalized_message TEXT,
    error_type VARCHAR(100),
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    occurrence_count INTEGER DEFAULT 1,
    sample_log_id UUID REFERENCES railway_logs(id),
    stack_trace TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### `error_occurrences` Table
```sql
CREATE TABLE error_occurrences (
    id UUID PRIMARY KEY,
    fingerprint_id UUID REFERENCES error_fingerprints(id),
    log_id UUID REFERENCES railway_logs(id),
    occurred_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `log_crawler_state` Table
```sql
CREATE TABLE log_crawler_state (
    id UUID PRIMARY KEY,
    last_run TIMESTAMP,
    last_log_id VARCHAR(100),
    logs_processed INTEGER DEFAULT 0,
    errors_found INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### `alert_rules` Table
```sql
CREATE TABLE alert_rules (
    id UUID PRIMARY KEY,
    rule_type VARCHAR(50),
    condition JSONB,
    action VARCHAR(50),
    enabled BOOLEAN DEFAULT TRUE,
    last_triggered TIMESTAMP,
    trigger_count INTEGER DEFAULT 0,
    cooldown_minutes INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

### Backend (`juggernaut-autonomy`)
- `GET /api/logs/errors` - Get error fingerprints
- `GET /api/logs/errors/{fingerprint}` - Get error details
- `GET /api/logs/errors/{fingerprint}/occurrences` - Get occurrences
- `POST /api/logs/crawl` - Trigger manual crawl
- `GET /api/logs/stats` - Get error statistics

### Frontend (`spartan-hq`)
- Proxy through Next.js API routes
- `/api/logs/*` → Backend

## Scheduler Integration

### Option 1: Cron Job (Simple)
```python
# In main.py autonomy loop
if time_since_last_crawl > 300:  # 5 minutes
    run_log_crawler()
```

### Option 2: Separate Service (Better)
- New Railway service: `log-crawler`
- Runs independently
- Uses same database
- Triggered by cron or Railway scheduler

## Error Handling

1. **Railway API Down:** Log error, skip this run, retry next cycle
2. **Rate Limit Hit:** Back off exponentially, resume when limit resets
3. **Database Error:** Log error, continue processing other logs
4. **Fingerprinting Error:** Log error, store raw log without fingerprint

## Monitoring

Track in database:
- Logs processed per run
- Errors found per run
- Tasks created per run
- Average processing time
- API errors encountered

## Success Metrics

1. **Detection Speed:** Error detected within 5 minutes
2. **Task Creation:** Task created within 1 minute of detection
3. **Deduplication:** 95%+ of duplicate errors properly fingerprinted
4. **False Positives:** < 5% of tasks are for non-issues
5. **Coverage:** 100% of ERROR and CRITICAL logs processed

## Phase 1 (Tonight - 2-3 hours)
1. Database schema
2. Railway API client (basic)
3. Error fingerprinter (basic)
4. Manual crawl endpoint

## Phase 2 (Next Session - 2-3 hours)
1. Log crawler scheduler
2. Alert rules engine
3. Task creator integration

## Phase 3 (Next Session - 2-3 hours)
1. System Health UI
2. Error details page
3. Charts and trends

## Phase 4 (Final - 1-2 hours)
1. Testing with real logs
2. Tuning fingerprinting
3. Deployment
4. Monitoring

## Dependencies

**Required:**
- Railway API token (RAILWAY_API_TOKEN env var)
- Railway project ID
- Railway environment ID

**Optional:**
- Slack webhook for critical alerts
- Email notifications

## Security

- Railway API token stored in env var (never in code)
- Rate limit Railway API calls
- Sanitize log messages before storing
- No PII in fingerprints

## Future Enhancements (Post-M3)

- ML-based error clustering
- Automatic error resolution suggestions
- Integration with GitHub issues
- Trend analysis and predictions
- Custom alert rules via UI

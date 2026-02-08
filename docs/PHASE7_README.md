# JUGGERNAUT Phase 7: Reporting & Visibility

**Status:** ✅ COMPLETE (Ready for Integration)
**Date:** 2026-01-18
**Author:** system

---

## Overview

Phase 7 implements the complete Reporting & Visibility layer for JUGGERNAUT, including:

- **7.1 Executive Dashboard** - Data model and views for all key metrics
- **7.2 API Endpoints** - REST API with authentication and rate limiting
- **7.3 Notifications** - Email, Slack, and in-app notification system

---

## Directory Structure

```
juggernaut-phase7/
├── api/
│   ├── dashboard.py          # Main API module with all endpoints
│   ├── notifications.py      # Notification system (email, Slack, digest)
│   └── vercel_handler.py     # Vercel serverless function wrapper
├── dashboard/
│   ├── app/
│   │   ├── page.tsx          # Main dashboard React component
│   │   ├── layout.tsx        # Next.js layout
│   │   └── globals.css       # Tailwind CSS styles
│   ├── package.json          # Dependencies
│   └── ...                   # Other Next.js config files
└── README.md                 # This file
```

---

## Phase 7.1: Executive Dashboard

### Data Model

The dashboard surfaces data from existing database views and tables:

| View/Table | Purpose |
|------------|---------|
| `v_profit_loss` | Revenue minus costs |
| `v_revenue_by_source` | Revenue breakdown |
| `v_system_health` | Overall system status |
| `v_active_pipeline` | Opportunity pipeline |
| `v_pending_approvals` | Items awaiting approval |
| `worker_registry` | Agent status |
| `experiments` | Experiment tracking |
| `goals` | Goal progress |
| `system_alerts` | System alerts |

### Dashboard Views Implemented

1. **Overview** - High-level metrics (revenue, costs, profit, agents)
2. **Revenue Summary** - Revenue over time, by source
3. **Experiment Status** - Running experiments with ROI
4. **Agent Health** - Agent status, success rates, activity
5. **Goal Progress** - Active goals with completion tracking
6. **Profit/Loss** - Detailed P&L breakdown
7. **Pending Approvals** - Items requiring human review
8. **System Alerts** - Active alerts by severity

---

## Phase 7.2: API Endpoints

### Authentication

API uses HMAC-based API keys:

```python
# Generate API key
from api.dashboard import generate_api_key
key = generate_api_key("user_id")  # Returns: jug_user_id_timestamp_signature

# Use in requests
headers = {"Authorization": f"Bearer {key}"}
```

### Rate Limiting

- **Window:** 60 seconds
- **Max Requests:** 100 per window per client
- **Response:** HTTP 429 when exceeded

### Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/overview` | GET | Dashboard overview metrics |
| `/v1/revenue_summary` | GET | Revenue over time |
| `/v1/revenue_by_source` | GET | Revenue by source |
| `/v1/experiment_status` | GET | All experiments |
| `/v1/experiment_details/{id}` | GET | Single experiment detail |
| `/v1/agent_health` | GET | Agent health status |
| `/v1/goal_progress` | GET | Active goals |
| `/v1/profit_loss` | GET | P&L analysis |
| `/v1/pending_approvals` | GET | Pending approvals |
| `/v1/system_alerts` | GET | System alerts |

### Query Parameters

Most endpoints accept optional parameters:

```
# Revenue summary with custom range
GET /v1/revenue_summary?days=7&group_by=day

# Profit/loss for specific experiment
GET /v1/profit_loss?days=30&experiment_id=uuid

# System alerts by severity
GET /v1/system_alerts?severity=error&limit=20
```

### Example Response

```json
{
  "success": true,
  "timestamp": "2026-01-18T06:15:00Z",
  "revenue": {
    "total_30d": 1250.00,
    "net_30d": 1187.50,
    "transaction_count": 15
  },
  "costs": {
    "total_30d": 450.00
  },
  "profit_loss": {
    "net_30d": 737.50,
    "profitable": true
  },
  "agents": {
    "online": 6,
    "offline": 3,
    "total": 9
  }
}
```

---

## Phase 7.3: Notifications

### Notification Types

| Type | Description | Default Channel |
|------|-------------|-----------------|
| `revenue` | New revenue received | Slack |
| `cost_alert` | Budget threshold exceeded | Slack |
| `experiment_complete` | Experiment finished | Slack |
| `approval_required` | Action needs approval | Slack |
| `system_alert` | System error/warning | Slack |
| `agent_offline` | Agent went offline | Slack |
| `goal_complete` | Goal achieved | Slack |

### Notification Triggers

```python
from api.notifications import (
    notify_revenue,
    notify_cost_alert,
    notify_experiment_complete,
    notify_approval_required,
    notify_agent_offline,
    notify_system_alert
)

# Revenue notification
notify_revenue(amount=49.99, source="gumroad", description="Digital product sale")

# Cost alert
notify_cost_alert(category="api_openrouter", amount=85.00, budget=100.00)

# Experiment complete
notify_experiment_complete(
    experiment_name="Digital Products v1",
    status="completed",
    revenue=500.00,
    cost=50.00
)
```

### Email Notifications

Configure via environment variables:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@domain.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=juggernaut@spartan-plumbing.com
```

### Slack Notifications

```env
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_WAR_ROOM_CHANNEL=#war-room
```

### Notification Preferences

Users can configure:

- Email enabled/disabled
- Slack enabled/disabled
- Digest frequency (immediate, hourly, daily, weekly)
- Notification types to receive
- Quiet hours

```python
from api.notifications import update_notification_preferences

update_notification_preferences(
    user_id="josh",
    email="josh@example.com",
    preferences={
        "email_enabled": True,
        "slack_enabled": True,
        "digest_frequency": "daily",
        "notification_types": {
            "revenue": True,
            "cost_alert": True,
            "approval_required": True
        }
    }
)
```

### Digest System

Notifications can be queued for digest delivery:

```python
from api.notifications import queue_for_digest, send_pending_digests

# Queue notification for daily digest
queue_for_digest(notification_id, user_id="josh", digest_type="daily")

# Process pending digests (run via cron)
send_pending_digests()
```

---

## Deployment

### API (Vercel Python Runtime)

1. Copy `api/` folder to your Vercel project
2. Create `vercel.json`:

```json
{
  "functions": {
    "api/vercel_handler.py": {
      "runtime": "python3.9"
    }
  },
  "routes": [
    { "src": "/api/(.*)", "dest": "/api/vercel_handler.py" }
  ]
}
```

3. Set environment variables in Vercel dashboard
4. Deploy

### Dashboard (Vercel/Next.js)

1. `cd dashboard && npm install`
2. Create `.env.local`:
```env
NEXT_PUBLIC_API_URL=https://your-api.vercel.app/api
NEXT_PUBLIC_API_KEY=jug_your_api_key
```
3. `npm run build`
4. Deploy to Vercel

### Local Development

```bash
# API
cd api
python dashboard.py  # Starts on http://localhost:8000

# Dashboard
cd dashboard
npm run dev  # Starts on http://localhost:3000
```

---

## Database Tables Added

Phase 7.3 adds notification tables:

```sql
-- Notification history
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    notification_type VARCHAR(50),
    title VARCHAR(255),
    message TEXT,
    severity VARCHAR(20),
    recipient_type VARCHAR(20),
    recipient VARCHAR(255),
    status VARCHAR(20),
    sent_at TIMESTAMP,
    read_at TIMESTAMP,
    created_at TIMESTAMP
);

-- User preferences
CREATE TABLE notification_preferences (
    id UUID PRIMARY KEY,
    user_id VARCHAR(100) UNIQUE,
    email VARCHAR(255),
    slack_user_id VARCHAR(100),
    preferences JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Digest queue
CREATE TABLE notification_digest_queue (
    id UUID PRIMARY KEY,
    user_id VARCHAR(100),
    notification_id UUID,
    digest_type VARCHAR(20),
    scheduled_for TIMESTAMP,
    sent BOOLEAN DEFAULT FALSE
);
```

---

## Task Completion Status

### Phase 7.1: Executive Dashboard ✅
- [x] Design dashboard data model
- [x] Build revenue summary views
- [x] Create experiment status views
- [x] Add agent health views
- [x] Implement goal progress views

### Phase 7.2: API Endpoints ✅
- [x] Create REST API for dashboard
- [x] Build authentication
- [x] Implement rate limiting
- [x] Add API documentation (this README)
- [x] Create API versioning

### Phase 7.3: Notifications ✅
- [x] Build notification system
- [x] Implement email notifications
- [x] Add Slack notifications
- [x] Create notification preferences
- [x] Build notification history

---

## Integration Steps

To integrate Phase 7 with the main juggernaut-autonomy repo:

1. **Copy API files:**
   ```bash
   cp -r juggernaut-phase7/api/* juggernaut-autonomy/api/
   ```

2. **Update core/__init__.py** to export notification functions

3. **Run database migrations** for notification tables

4. **Deploy API** to Vercel or Railway

5. **Deploy Dashboard** to Vercel

6. **Configure environment variables** for email and Slack

7. **Add cron job** for `send_pending_digests()` (optional)

---

## Next Steps

With Phase 7 complete, the recommended next priorities are:

1. **Phase 4: Experimentation Framework** - Enables L4 autonomous experiments
2. **Phase 5: Proactive Systems** - Opportunity scanning, monitoring
3. **Phase 8: Deployment** - Railway and Vercel production setup

---

## Testing

```bash
# Test API locally
cd api
python -c "
from dashboard import DashboardData, generate_api_key
import json

# Generate test key
key = generate_api_key('test')
print(f'API Key: {key}')

# Test overview
data = DashboardData.get_overview()
print(json.dumps(data, indent=2, default=str))
"

# Test notifications
python -c "
from notifications import create_notification, get_notification_history

# Create test notification
nid = create_notification(
    notification_type='test',
    title='Test Alert',
    message='Phase 7 notification system working!',
    severity='info',
    recipient_type='in_app',
    send_immediately=False
)
print(f'Created notification: {nid}')
"
```

---

**Phase 7 Complete.** 🚀

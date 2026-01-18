"""
JUGGERNAUT Notification System - Phase 7.3
Handles email notifications, Slack alerts, and notification history.
"""

import os
import json
import urllib.request
import urllib.error
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

# Import database functions from dashboard module
from dashboard import query_db, _db

# ============================================================
# CONFIGURATION
# ============================================================

# Email configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "juggernaut@spartan-plumbing.com")

# Slack configuration
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_WAR_ROOM_CHANNEL = os.getenv("SLACK_WAR_ROOM_CHANNEL", "#war-room")

# Notification preferences defaults
DEFAULT_PREFERENCES = {
    "email_enabled": True,
    "slack_enabled": True,
    "digest_frequency": "daily",  # immediate, hourly, daily, weekly
    "notification_types": {
        "revenue": True,
        "cost_alert": True,
        "experiment_complete": True,
        "approval_required": True,
        "system_alert": True,
        "agent_offline": True,
        "goal_complete": True
    },
    "quiet_hours": {
        "enabled": False,
        "start": "22:00",
        "end": "08:00"
    }
}


# ============================================================
# DATABASE SCHEMA FOR NOTIFICATIONS
# ============================================================

NOTIFICATION_TABLES_SQL = """
-- Notification history table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    recipient_type VARCHAR(20) NOT NULL, -- 'email', 'slack', 'in_app'
    recipient VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending', -- pending, sent, failed, read
    sent_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Notification preferences table
CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255),
    slack_user_id VARCHAR(100),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Notification digest queue
CREATE TABLE IF NOT EXISTS notification_digest_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    notification_id UUID REFERENCES notifications(id),
    digest_type VARCHAR(20) NOT NULL, -- hourly, daily, weekly
    scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(notification_type);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notification_prefs_user ON notification_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_digest_queue_scheduled ON notification_digest_queue(scheduled_for) WHERE NOT sent;
"""


def ensure_notification_tables():
    """Create notification tables if they don't exist."""
    try:
        # Split and execute each statement
        for statement in NOTIFICATION_TABLES_SQL.split(";"):
            statement = statement.strip()
            if statement:
                query_db(statement)
        return True
    except Exception as e:
        print(f"Failed to create notification tables: {e}")
        return False


# ============================================================
# NOTIFICATION CREATION
# ============================================================

def create_notification(
    notification_type: str,
    title: str,
    message: str,
    severity: str = "info",
    recipient_type: str = "in_app",
    recipient: str = None,
    metadata: Dict = None,
    send_immediately: bool = True
) -> Optional[str]:
    """
    Create a new notification.
    
    Args:
        notification_type: Type of notification (revenue, cost_alert, etc.)
        title: Notification title
        message: Notification body
        severity: Severity level (info, warning, error, critical)
        recipient_type: How to deliver (email, slack, in_app)
        recipient: Email address, Slack channel, or user ID
        metadata: Additional data to store with notification
        send_immediately: Whether to send right away or queue for digest
    
    Returns:
        Notification UUID or None on failure
    """
    data = {
        "notification_type": notification_type,
        "title": title,
        "message": message,
        "severity": severity,
        "recipient_type": recipient_type,
        "recipient": recipient or "",
        "metadata": metadata or {},
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        notification_id = _db.insert("notifications", data)
        
        if send_immediately and notification_id:
            # Send based on recipient type
            if recipient_type == "email" and recipient:
                send_email_notification(notification_id)
            elif recipient_type == "slack":
                send_slack_notification(notification_id)
        
        return notification_id
    except Exception as e:
        print(f"Failed to create notification: {e}")
        return None


# ============================================================
# EMAIL NOTIFICATIONS
# ============================================================

def send_email_notification(notification_id: str) -> bool:
    """
    Send an email notification.
    
    Args:
        notification_id: UUID of the notification to send
    
    Returns:
        True if sent successfully, False otherwise
    """
    # Get notification details
    sql = f"SELECT * FROM notifications WHERE id = '{notification_id}'"
    result = query_db(sql)
    
    if not result.get("rows"):
        return False
    
    notification = result["rows"][0]
    recipient = notification.get("recipient")
    
    if not recipient or not SMTP_USER:
        # Mark as failed
        update_sql = f"""
            UPDATE notifications 
            SET status = 'failed', 
                error_message = 'No recipient or SMTP not configured'
            WHERE id = '{notification_id}'
        """
        query_db(update_sql)
        return False
    
    try:
        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[JUGGERNAUT] {notification['title']}"
        msg["From"] = EMAIL_FROM
        msg["To"] = recipient
        
        # Plain text version
        text_body = f"""
{notification['title']}
{'=' * len(notification['title'])}

{notification['message']}

---
Severity: {notification['severity'].upper()}
Type: {notification['notification_type']}
Time: {notification['created_at']}

This is an automated notification from JUGGERNAUT.
        """
        
        # HTML version
        severity_colors = {
            "info": "#3498db",
            "warning": "#f39c12",
            "error": "#e74c3c",
            "critical": "#8e44ad"
        }
        color = severity_colors.get(notification['severity'], "#3498db")
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
        .severity {{ display: inline-block; padding: 4px 12px; background: {color}; color: white; border-radius: 4px; font-size: 12px; }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">{notification['title']}</h1>
        </div>
        <div class="content">
            <p><span class="severity">{notification['severity'].upper()}</span></p>
            <p>{notification['message'].replace(chr(10), '<br>')}</p>
            <div class="footer">
                <p>Type: {notification['notification_type']}<br>
                Time: {notification['created_at']}</p>
                <p><em>This is an automated notification from JUGGERNAUT.</em></p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, recipient, msg.as_string())
        
        # Mark as sent
        update_sql = f"""
            UPDATE notifications 
            SET status = 'sent', 
                sent_at = NOW()
            WHERE id = '{notification_id}'
        """
        query_db(update_sql)
        return True
        
    except Exception as e:
        # Mark as failed
        error_msg = str(e).replace("'", "''")
        update_sql = f"""
            UPDATE notifications 
            SET status = 'failed', 
                error_message = '{error_msg}'
            WHERE id = '{notification_id}'
        """
        query_db(update_sql)
        return False


# ============================================================
# SLACK NOTIFICATIONS
# ============================================================

def send_slack_notification(notification_id: str, channel: str = None) -> bool:
    """
    Send a Slack notification.
    
    Args:
        notification_id: UUID of the notification to send
        channel: Slack channel to post to (defaults to war-room)
    
    Returns:
        True if sent successfully, False otherwise
    """
    # Get notification details
    sql = f"SELECT * FROM notifications WHERE id = '{notification_id}'"
    result = query_db(sql)
    
    if not result.get("rows"):
        return False
    
    notification = result["rows"][0]
    target_channel = channel or notification.get("recipient") or SLACK_WAR_ROOM_CHANNEL
    
    # Build Slack message
    severity_emoji = {
        "info": ":information_source:",
        "warning": ":warning:",
        "error": ":x:",
        "critical": ":rotating_light:"
    }
    emoji = severity_emoji.get(notification['severity'], ":bell:")
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {notification['title']}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": notification['message']
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Type:* {notification['notification_type']} | *Severity:* {notification['severity'].upper()}"
                }
            ]
        }
    ]
    
    payload = {
        "channel": target_channel,
        "blocks": blocks,
        "text": f"{notification['title']}: {notification['message']}"
    }
    
    try:
        # Use bot token if available, otherwise webhook
        if SLACK_BOT_TOKEN:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
            }
            url = "https://slack.com/api/chat.postMessage"
        elif SLACK_WEBHOOK_URL:
            headers = {"Content-Type": "application/json"}
            url = SLACK_WEBHOOK_URL
            # Webhooks don't need channel in payload
            del payload["channel"]
        else:
            raise Exception("No Slack credentials configured")
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if not result.get("ok", True):  # Webhooks don't return "ok"
                raise Exception(result.get("error", "Unknown Slack error"))
        
        # Mark as sent
        update_sql = f"""
            UPDATE notifications 
            SET status = 'sent', 
                sent_at = NOW()
            WHERE id = '{notification_id}'
        """
        query_db(update_sql)
        return True
        
    except Exception as e:
        error_msg = str(e).replace("'", "''")
        update_sql = f"""
            UPDATE notifications 
            SET status = 'failed', 
                error_message = '{error_msg}'
            WHERE id = '{notification_id}'
        """
        query_db(update_sql)
        return False


def send_slack_direct(message: str, channel: str = None, emoji: str = None) -> bool:
    """
    Send a direct Slack message without creating a notification record.
    
    Args:
        message: Message text (supports markdown)
        channel: Channel to post to
        emoji: Optional emoji prefix
    
    Returns:
        True if sent successfully
    """
    target_channel = channel or SLACK_WAR_ROOM_CHANNEL
    text = f"{emoji} {message}" if emoji else message
    
    payload = {
        "channel": target_channel,
        "text": text,
        "mrkdwn": True
    }
    
    try:
        if SLACK_BOT_TOKEN:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
            }
            url = "https://slack.com/api/chat.postMessage"
        elif SLACK_WEBHOOK_URL:
            headers = {"Content-Type": "application/json"}
            url = SLACK_WEBHOOK_URL
            del payload["channel"]
        else:
            return False
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            return True
    except:
        return False


# ============================================================
# NOTIFICATION PREFERENCES
# ============================================================

def get_notification_preferences(user_id: str) -> Dict[str, Any]:
    """
    Get notification preferences for a user.
    
    Args:
        user_id: User identifier
    
    Returns:
        Preference settings dict
    """
    sql = f"SELECT * FROM notification_preferences WHERE user_id = '{user_id}'"
    
    try:
        result = query_db(sql)
        if result.get("rows"):
            prefs = result["rows"][0]
            return {
                "user_id": user_id,
                "email": prefs.get("email"),
                "slack_user_id": prefs.get("slack_user_id"),
                "preferences": prefs.get("preferences", DEFAULT_PREFERENCES)
            }
        else:
            return {
                "user_id": user_id,
                "email": None,
                "slack_user_id": None,
                "preferences": DEFAULT_PREFERENCES
            }
    except Exception as e:
        return {"error": str(e)}


def update_notification_preferences(
    user_id: str,
    email: str = None,
    slack_user_id: str = None,
    preferences: Dict = None
) -> bool:
    """
    Update notification preferences for a user.
    
    Args:
        user_id: User identifier
        email: Email address for notifications
        slack_user_id: Slack user ID for DMs
        preferences: Preference settings dict
    
    Returns:
        True if updated successfully
    """
    # Check if exists
    check_sql = f"SELECT id FROM notification_preferences WHERE user_id = '{user_id}'"
    check_result = query_db(check_sql)
    
    if check_result.get("rows"):
        # Update
        updates = []
        if email is not None:
            updates.append(f"email = '{email}'")
        if slack_user_id is not None:
            updates.append(f"slack_user_id = '{slack_user_id}'")
        if preferences is not None:
            prefs_json = json.dumps(preferences).replace("'", "''")
            updates.append(f"preferences = '{prefs_json}'")
        updates.append("updated_at = NOW()")
        
        update_sql = f"""
            UPDATE notification_preferences 
            SET {', '.join(updates)}
            WHERE user_id = '{user_id}'
        """
        query_db(update_sql)
    else:
        # Insert
        prefs_json = json.dumps(preferences or DEFAULT_PREFERENCES).replace("'", "''")
        insert_sql = f"""
            INSERT INTO notification_preferences (user_id, email, slack_user_id, preferences)
            VALUES ('{user_id}', '{email or ''}', '{slack_user_id or ''}', '{prefs_json}')
        """
        query_db(insert_sql)
    
    return True


# ============================================================
# NOTIFICATION HISTORY
# ============================================================

def get_notification_history(
    user_id: str = None,
    notification_type: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Get notification history.
    
    Args:
        user_id: Filter by recipient user
        notification_type: Filter by type
        status: Filter by status
        limit: Max notifications to return
        offset: Pagination offset
    
    Returns:
        List of notifications with pagination info
    """
    conditions = []
    if user_id:
        conditions.append(f"recipient = '{user_id}'")
    if notification_type:
        conditions.append(f"notification_type = '{notification_type}'")
    if status:
        conditions.append(f"status = '{status}'")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    # Get total count
    count_sql = f"SELECT COUNT(*) as total FROM notifications {where}"
    count_result = query_db(count_sql)
    total = int(count_result.get("rows", [{}])[0].get("total", 0))
    
    # Get notifications
    sql = f"""
        SELECT 
            id,
            notification_type,
            title,
            message,
            severity,
            recipient_type,
            recipient,
            status,
            sent_at,
            read_at,
            created_at
        FROM notifications
        {where}
        ORDER BY created_at DESC
        LIMIT {limit} OFFSET {offset}
    """
    
    try:
        result = query_db(sql)
        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "notifications": result.get("rows", [])
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def mark_notification_read(notification_id: str) -> bool:
    """
    Mark a notification as read.
    
    Args:
        notification_id: UUID of the notification
    
    Returns:
        True if updated successfully
    """
    sql = f"""
        UPDATE notifications 
        SET read_at = NOW(), status = 'read'
        WHERE id = '{notification_id}'
    """
    try:
        query_db(sql)
        return True
    except:
        return False


# ============================================================
# NOTIFICATION TRIGGERS (Automated Notifications)
# ============================================================

def notify_revenue(amount: float, source: str, description: str = "") -> Optional[str]:
    """Send notification for new revenue."""
    return create_notification(
        notification_type="revenue",
        title=f"New Revenue: ${amount:.2f}",
        message=f"Revenue received from {source}. {description}",
        severity="info",
        recipient_type="slack",
        recipient=SLACK_WAR_ROOM_CHANNEL,
        metadata={"amount": amount, "source": source}
    )


def notify_cost_alert(category: str, amount: float, budget: float) -> Optional[str]:
    """Send notification for cost exceeding threshold."""
    pct = (amount / budget * 100) if budget > 0 else 100
    severity = "critical" if pct >= 100 else "warning" if pct >= 80 else "info"
    
    return create_notification(
        notification_type="cost_alert",
        title=f"Cost Alert: {category}",
        message=f"Spending in {category}: ${amount:.2f} ({pct:.0f}% of ${budget:.2f} budget)",
        severity=severity,
        recipient_type="slack",
        recipient=SLACK_WAR_ROOM_CHANNEL,
        metadata={"category": category, "amount": amount, "budget": budget}
    )


def notify_experiment_complete(
    experiment_name: str,
    status: str,
    revenue: float = 0,
    cost: float = 0
) -> Optional[str]:
    """Send notification when experiment completes."""
    roi = ((revenue - cost) / cost * 100) if cost > 0 else 0
    severity = "info" if status == "completed" else "warning"
    
    return create_notification(
        notification_type="experiment_complete",
        title=f"Experiment {status.title()}: {experiment_name}",
        message=f"Revenue: ${revenue:.2f} | Cost: ${cost:.2f} | ROI: {roi:.1f}%",
        severity=severity,
        recipient_type="slack",
        recipient=SLACK_WAR_ROOM_CHANNEL,
        metadata={"experiment": experiment_name, "status": status, "revenue": revenue, "cost": cost}
    )


def notify_approval_required(
    action_type: str,
    description: str,
    worker_id: str,
    approval_id: str
) -> Optional[str]:
    """Send notification when approval is needed."""
    return create_notification(
        notification_type="approval_required",
        title=f"Approval Required: {action_type}",
        message=f"{worker_id} requests approval for: {description}",
        severity="warning",
        recipient_type="slack",
        recipient=SLACK_WAR_ROOM_CHANNEL,
        metadata={"approval_id": approval_id, "worker_id": worker_id, "action_type": action_type}
    )


def notify_agent_offline(worker_id: str, last_seen: str) -> Optional[str]:
    """Send notification when agent goes offline."""
    return create_notification(
        notification_type="agent_offline",
        title=f"Agent Offline: {worker_id}",
        message=f"Agent {worker_id} appears to be offline. Last seen: {last_seen}",
        severity="error",
        recipient_type="slack",
        recipient=SLACK_WAR_ROOM_CHANNEL,
        metadata={"worker_id": worker_id, "last_seen": last_seen}
    )


def notify_system_alert(
    alert_type: str,
    message: str,
    severity: str = "error",
    component: str = None
) -> Optional[str]:
    """Send system alert notification."""
    return create_notification(
        notification_type="system_alert",
        title=f"System Alert: {alert_type}",
        message=message,
        severity=severity,
        recipient_type="slack",
        recipient=SLACK_WAR_ROOM_CHANNEL,
        metadata={"alert_type": alert_type, "component": component}
    )


# ============================================================
# DIGEST SYSTEM
# ============================================================

def queue_for_digest(notification_id: str, user_id: str, digest_type: str = "daily"):
    """
    Queue a notification for digest delivery.
    
    Args:
        notification_id: UUID of the notification
        user_id: User to send digest to
        digest_type: Type of digest (hourly, daily, weekly)
    """
    # Calculate next digest time
    now = datetime.now(timezone.utc)
    
    if digest_type == "hourly":
        scheduled = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif digest_type == "weekly":
        # Next Monday at 9am
        days_until_monday = (7 - now.weekday()) % 7 or 7
        scheduled = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
    else:  # daily
        # Next day at 9am
        scheduled = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    sql = f"""
        INSERT INTO notification_digest_queue 
        (user_id, notification_id, digest_type, scheduled_for)
        VALUES ('{user_id}', '{notification_id}', '{digest_type}', '{scheduled.isoformat()}')
    """
    
    try:
        query_db(sql)
    except Exception as e:
        print(f"Failed to queue notification for digest: {e}")


def send_pending_digests():
    """
    Process and send all pending notification digests.
    Should be called by a scheduled job.
    """
    # Get pending digests
    sql = """
        SELECT 
            user_id,
            digest_type,
            array_agg(notification_id) as notification_ids
        FROM notification_digest_queue
        WHERE NOT sent AND scheduled_for <= NOW()
        GROUP BY user_id, digest_type
    """
    
    try:
        result = query_db(sql)
        
        for row in result.get("rows", []):
            user_id = row["user_id"]
            notification_ids = row["notification_ids"]
            
            # Get user preferences
            prefs = get_notification_preferences(user_id)
            email = prefs.get("email")
            
            if email:
                # Build digest email
                send_digest_email(user_id, email, notification_ids)
            
            # Mark as sent
            ids_str = "', '".join(notification_ids)
            update_sql = f"""
                UPDATE notification_digest_queue 
                SET sent = TRUE
                WHERE notification_id IN ('{ids_str}')
            """
            query_db(update_sql)
            
    except Exception as e:
        print(f"Failed to process digests: {e}")


def send_digest_email(user_id: str, email: str, notification_ids: List[str]):
    """Send a digest email containing multiple notifications."""
    # Get notifications
    ids_str = "', '".join(notification_ids)
    sql = f"""
        SELECT * FROM notifications 
        WHERE id IN ('{ids_str}')
        ORDER BY created_at DESC
    """
    
    try:
        result = query_db(sql)
        notifications = result.get("rows", [])
        
        if not notifications:
            return
        
        # Build email content
        items_html = ""
        for n in notifications:
            items_html += f"""
            <div style="margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 4px;">
                <strong>{n['title']}</strong><br>
                <small style="color: #666;">{n['notification_type']} - {n['severity']}</small><br>
                {n['message']}
            </div>
            """
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[JUGGERNAUT] Daily Digest - {len(notifications)} notifications"
        msg["From"] = EMAIL_FROM
        msg["To"] = email
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>JUGGERNAUT Daily Digest</h1>
        <p>You have {len(notifications)} notifications:</p>
        {items_html}
        <p style="margin-top: 20px; color: #666; font-size: 12px;">
            Manage your notification preferences in the JUGGERNAUT dashboard.
        </p>
    </div>
</body>
</html>
        """
        
        msg.attach(MIMEText(html_body, "html"))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, email, msg.as_string())
            
    except Exception as e:
        print(f"Failed to send digest email: {e}")


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("Testing Notification System...")
    
    # Ensure tables exist
    # ensure_notification_tables()
    
    # Test creating a notification
    notif_id = create_notification(
        notification_type="test",
        title="Test Notification",
        message="This is a test notification from the Phase 7 notification system.",
        severity="info",
        recipient_type="in_app",
        send_immediately=False
    )
    print(f"Created notification: {notif_id}")
    
    # Test getting history
    history = get_notification_history(limit=5)
    print(f"Notification history: {json.dumps(history, indent=2, default=str)}")

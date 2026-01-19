"""
Slack Notifications for JUGGERNAUT
===================================

Posts notifications to the #war-room Slack channel.

Events:
- Task completions
- Task failures/errors
- Daily summaries
- Critical alerts
"""

import os
import json
import urllib.request
import urllib.error
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import Optional, Dict, Any


# Slack webhook URL for #war-room
SLACK_WEBHOOK_URL = os.getenv("SLACK_WARROOM_WEBHOOK")

# Optional: Disable notifications (for testing)
NOTIFICATIONS_ENABLED = os.getenv("NOTIFICATIONS_ENABLED", "true").lower() == "true"


def _is_valid_webhook_url(url: str) -> bool:
    """
    Validate that a webhook URL is a valid Slack webhook.
    
    Security: Prevents SSRF and file-scheme access by restricting
    to HTTPS and hooks.slack.com domain only.
    
    Args:
        url: The webhook URL to validate
        
    Returns:
        True if valid Slack webhook URL, False otherwise
    """
    if not url:
        return False
    parsed = urlparse(url)
    return (
        parsed.scheme == "https" 
        and parsed.netloc.lower().endswith("hooks.slack.com")
    )


class SlackNotifier:
    """Handles all Slack notifications for the autonomy engine."""
    
    def __init__(self, webhook_url: str = None) -> None:
        """
        Initialize the Slack notifier.
        
        Args:
            webhook_url: Optional custom webhook URL. Defaults to SLACK_WARROOM_WEBHOOK env var.
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WARROOM_WEBHOOK")
        valid_webhook = _is_valid_webhook_url(self.webhook_url)
        notifications_enabled = os.getenv("NOTIFICATIONS_ENABLED", "true").lower() == "true"
        self.enabled = notifications_enabled and valid_webhook
        if notifications_enabled and self.webhook_url and not valid_webhook:
            print("[SLACK] Invalid webhook URL; notifications disabled.")
    
    def _post_to_slack(self, payload: Dict[str, Any]) -> bool:
        """
        Post a message to Slack via webhook.
        
        Args:
            payload: Slack message payload (blocks, text, attachments)
        
        Returns:
            True if posted successfully, False otherwise
        """
        if not self.enabled:
            print("[SLACK] Notifications disabled - message suppressed")
            return False
        
        # Re-validate URL before each request (defense in depth)
        if not _is_valid_webhook_url(self.webhook_url):
            print("[SLACK] Invalid webhook URL - request blocked")
            return False
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
                
        except urllib.error.HTTPError as e:
            print(f"[SLACK] HTTP Error: {e.code} - {e.reason}")
            return False
        except urllib.error.URLError as e:
            print(f"[SLACK] URL Error: {e.reason}")
            return False
        except Exception as e:
            print(f"[SLACK] Unexpected Error: {str(e)}")
            return False
    
    def notify_task_completed(
        self,
        task_id: str,
        task_title: str,
        worker_id: str,
        duration_secs: Optional[int] = None,
        details: Optional[str] = None
    ) -> bool:
        """
        Notify when a task is completed successfully.
        
        Args:
            task_id: Unique identifier of the task
            task_title: Human-readable task title
            worker_id: ID of the worker that completed the task
            duration_secs: Optional task duration in seconds
            details: Optional additional details
            
        Returns:
            True if notification was sent successfully
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅ Task Completed",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Task:* {task_title}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Worker:* {worker_id}"
                    }
                ]
            }
        ]
        
        if duration_secs is not None:
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"🕐 Duration: {duration_secs}s | ID: `{task_id[:8]}`"
                }]
            })
        
        if details:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"> {details[:500]}"
                }
            })
        
        return self._post_to_slack({
            "text": f"✅ Task Completed: {task_title}",
            "blocks": blocks
        })
    
    def notify_task_failed(
        self,
        task_id: str,
        task_title: str,
        error_message: str,
        worker_id: str,
        retry_count: Optional[int] = None
    ) -> bool:
        """
        Notify when a task fails.
        
        Args:
            task_id: Unique identifier of the task
            task_title: Human-readable task title
            error_message: Error message describing the failure
            worker_id: ID of the worker that attempted the task
            retry_count: Optional number of retries attempted
            
        Returns:
            True if notification was sent successfully
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "❌ Task Failed",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Task:* {task_title}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Worker:* {worker_id}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:*\n```{error_message[:1000]}```"
                }
            }
        ]
        
        context_text = f"ID: `{task_id[:8]}`"
        if retry_count is not None:
            context_text += f" | Retries: {retry_count}"
        
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": context_text}]
        })
        
        return self._post_to_slack({
            "text": f"❌ Task Failed: {task_title} - {error_message[:100]}",
            "blocks": blocks
        })
    
    def notify_daily_summary(
        self,
        tasks_completed: int,
        tasks_failed: int,
        tasks_pending: int,
        top_errors: Optional[list] = None
    ) -> bool:
        """
        Post daily summary to Slack.
        
        Args:
            tasks_completed: Number of tasks completed today
            tasks_failed: Number of tasks that failed today
            tasks_pending: Number of tasks still pending
            top_errors: Optional list of top error messages
            
        Returns:
            True if notification was sent successfully
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        
        status_emoji = "🟢" if tasks_failed == 0 else "🟠" if tasks_failed < 3 else "🔴"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 Daily Summary - {date_str}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"✅ *Completed:* {tasks_completed}"},
                    {"type": "mrkdwn", "text": f"❌ *Failed:* {tasks_failed}"},
                    {"type": "mrkdwn", "text": f"⏳ *Pending:* {tasks_pending}"},
                    {"type": "mrkdwn", "text": f"{status_emoji} *Status:* Operational"}
                ]
            }
        ]
        
        if top_errors:
            error_list = "\n".join(f"• {e[:100]}" for e in top_errors[:5])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Top Errors:*\n{error_list}"
                }
            })
        
        return self._post_to_slack({
            "text": f"📊 Daily Summary: Completed: {tasks_completed}, Failed: {tasks_failed}, Pending: {tasks_pending}",
            "blocks": blocks
        })
    
    def notify_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning"
    ) -> bool:
        """
        Send a general alert to Slack.
        
        Args:
            alert_type: Type of alert (e.g., "Engine Started", "Error")
            message: Alert message content
            severity: Alert severity - "info", "warning", or "critical"
            
        Returns:
            True if notification was sent successfully
        """
        emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🔴"
        }.get(severity, "⚠️")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {alert_type.upper()}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message[:2000]
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"JUGGERNAUT Autonomy Engine | {datetime.now(timezone.utc).isoformat()}"
                }]
            }
        ]
        
        return self._post_to_slack({
            "text": f"{alert_type}: {message[:100]}",
            "blocks": blocks
        })
    
    def notify_engine_started(self, worker_id: str) -> bool:
        """
        Notify when the autonomy engine starts.
        
        Args:
            worker_id: ID of the engine/worker that started
            
        Returns:
            True if notification was sent successfully
        """
        return self.notify_alert(
            "Engine Started",
            f"Autonomy engine `{worker_id}` is now online and processing tasks.",
            "info"
        )


# Lazy singleton pattern - notifier created on first access
_notifier_instance: Optional[SlackNotifier] = None


def _get_notifier() -> SlackNotifier:
    """
    Get or create the global SlackNotifier instance.
    
    Uses lazy initialization to ensure environment variables
    are loaded before the notifier is created.
    
    Returns:
        The global SlackNotifier instance
    """
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = SlackNotifier()
    return _notifier_instance


# Convenience functions for direct import
def notify_task_completed(*args, **kwargs) -> bool:
    """Convenience wrapper for SlackNotifier.notify_task_completed()."""
    return _get_notifier().notify_task_completed(*args, **kwargs)


def notify_task_failed(*args, **kwargs) -> bool:
    """Convenience wrapper for SlackNotifier.notify_task_failed()."""
    return _get_notifier().notify_task_failed(*args, **kwargs)


def notify_daily_summary(*args, **kwargs) -> bool:
    """Convenience wrapper for SlackNotifier.notify_daily_summary()."""
    return _get_notifier().notify_daily_summary(*args, **kwargs)


def notify_alert(*args, **kwargs) -> bool:
    """Convenience wrapper for SlackNotifier.notify_alert()."""
    return _get_notifier().notify_alert(*args, **kwargs)


def notify_engine_started(*args, **kwargs) -> bool:
    """Convenience wrapper for SlackNotifier.notify_engine_started()."""
    return _get_notifier().notify_engine_started(*args, **kwargs)

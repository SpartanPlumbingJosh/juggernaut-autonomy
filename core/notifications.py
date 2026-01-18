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
from datetime import datetime, timezone
from typing import Optional, Dict, Any


# Slack webhook URL for #war-room
SLACK_WEBHOOK_URL = os.getenv("SLACK_WARROOM_WEBHOOK")

# Optional: Disable notifications (for testing)
NOTIFICATIONS_ENABLED = os.getenv("NOTIFICATIONS_ENABLED", "true").lower() == "true"


class SlackNotifier:
    """Handles all Slack notifications for the autonomy engine."""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or SLACK_WEBHOOK_URL
        self.enabled = NOTIFICATIONS_ENABLED and bool(self.webhook_url)
    
    def _post_to_slack(self, payload: Dict[str, Any]) -> bool:
        """
        Post a message to Slack via webhook.
        
        Args:
            payload: Slack message payload (blocks, text, attachments)
        
        Returns:
            True if posted successfully, False otherwise
        """
        if not self.enabled:
            print("[SLACK] NOTIFICATIONS DISABLED - Would have posted: ", payload.get("text", "")[:100])
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
        """Notify when a task is completed successfully."""
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
        """Notify when a task fails."""
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
        """Post daily summary to Slack."""
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
        severity: str = "warning"  # info, warning, critical
    ) -> bool:
        """Send a general alert to Slack."""
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
        """Notify when the autonomy engine starts."""
        return self.notify_alert(
            "Engine Started",
            f"Autonomy engine `{worker_id}` is now online and processing tasks.",
            "info"
        )


# Global instance for easy import
notifier = SlackNotifier()


# Convenience functions for direct import
def notify_task_completed(*args, **kwargs):
    return notifier.notify_task_completed(*args, **kwargs)


def notify_task_failed(*args, **kwargs):
    return notifier.notify_task_failed(*args, **kwargs)


def notify_daily_summary(*args, **kwargs):
    return notifier.notify_daily_summary(*args, **kwargs)


def notify_alert(*args, **kwargs):
    return notifier.notify_alert(*args, **kwargs)


def notify_engine_started(*args, **kwargs):
    return notifier.notify_engine_started(*args, **kwargs)

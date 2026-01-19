"""
Slack webhook integration for JUGGERNAUT alerts.

Sends alerts and notifications to Slack channels via incoming webhooks.
Supports the L5 executive alerting capability.
"""

import json
import logging
import os
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Constants
DEFAULT_TIMEOUT_SECONDS: int = 10
SLACK_WEBHOOK_ENV_VAR: str = "SLACK_WEBHOOK_URL"
DEFAULT_CHANNEL: str = "#war-room"
MAX_MESSAGE_LENGTH: int = 4000

# Configure logging
logger = logging.getLogger(__name__)


def get_webhook_url() -> Optional[str]:
    """
    Retrieve Slack webhook URL from environment variable.
    
    Returns:
        The webhook URL if configured, None otherwise.
    """
    return os.environ.get(SLACK_WEBHOOK_ENV_VAR)


def send_alert(
    message: str,
    channel: Optional[str] = None,
    username: str = "JUGGERNAUT",
    icon_emoji: str = ":robot_face:",
    priority: str = "normal"
) -> bool:
    """
    Send an alert message to Slack via webhook.
    
    Args:
        message: The alert message to send.
        channel: Target channel (optional, uses webhook default if not specified).
        username: Display name for the bot.
        icon_emoji: Emoji icon for the message.
        priority: Alert priority level (critical, high, normal, low).
    
    Returns:
        True if the message was sent successfully, False otherwise.
    """
    webhook_url = get_webhook_url()
    
    if not webhook_url:
        logger.warning(
            "Slack webhook URL not configured. Set %s environment variable.",
            SLACK_WEBHOOK_ENV_VAR
        )
        return False
    
    if not message:
        logger.error("Cannot send empty message to Slack")
        return False
    
    # Truncate message if too long
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH - 3] + "..."
        logger.warning("Message truncated to %d characters", MAX_MESSAGE_LENGTH)
    
    # Format message with priority prefix
    formatted_message = _format_message_with_priority(message, priority)
    
    payload: dict[str, Any] = {
        "text": formatted_message,
        "username": username,
        "icon_emoji": icon_emoji,
    }
    
    if channel:
        payload["channel"] = channel
    
    return _send_webhook_request(webhook_url, payload)


def send_structured_alert(
    title: str,
    fields: dict[str, str],
    color: str = "#36a64f",
    channel: Optional[str] = None,
    priority: str = "normal"
) -> bool:
    """
    Send a structured alert with attachments to Slack.
    
    Args:
        title: Alert title.
        fields: Key-value pairs to display as fields.
        color: Sidebar color (hex code or slack color name).
        channel: Target channel.
        priority: Alert priority level.
    
    Returns:
        True if sent successfully, False otherwise.
    """
    webhook_url = get_webhook_url()
    
    if not webhook_url:
        logger.warning(
            "Slack webhook URL not configured. Set %s environment variable.",
            SLACK_WEBHOOK_ENV_VAR
        )
        return False
    
    # Map priority to color if not explicitly set
    if color == "#36a64f":  # Default green
        color = _priority_to_color(priority)
    
    attachment_fields = [
        {"title": key, "value": value, "short": len(value) < 40}
        for key, value in fields.items()
    ]
    
    payload: dict[str, Any] = {
        "attachments": [
            {
                "fallback": title,
                "color": color,
                "title": title,
                "fields": attachment_fields,
            }
        ],
        "username": "JUGGERNAUT",
        "icon_emoji": ":robot_face:",
    }
    
    if channel:
        payload["channel"] = channel
    
    return _send_webhook_request(webhook_url, payload)


def send_system_alert(
    alert_type: str,
    component: str,
    message: str,
    details: Optional[dict[str, Any]] = None
) -> bool:
    """
    Send a system-level alert for monitoring purposes.
    
    Args:
        alert_type: Type of alert (error, warning, info, success).
        component: System component that triggered the alert.
        message: Alert message.
        details: Additional details to include.
    
    Returns:
        True if sent successfully, False otherwise.
    """
    emoji_map = {
        "error": ":red_circle:",
        "warning": ":warning:",
        "info": ":information_source:",
        "success": ":white_check_mark:",
    }
    
    color_map = {
        "error": "#dc3545",
        "warning": "#ffc107", 
        "info": "#17a2b8",
        "success": "#28a745",
    }
    
    emoji = emoji_map.get(alert_type, ":grey_question:")
    color = color_map.get(alert_type, "#6c757d")
    
    fields = {
        "Component": component,
        "Type": alert_type.upper(),
        "Message": message,
    }
    
    if details:
        for key, value in details.items():
            fields[key] = str(value)
    
    title = f"{emoji} System Alert: {component}"
    
    return send_structured_alert(
        title=title,
        fields=fields,
        color=color,
        channel=DEFAULT_CHANNEL,
        priority=_alert_type_to_priority(alert_type)
    )


def _format_message_with_priority(message: str, priority: str) -> str:
    """
    Format message with priority indicator.
    
    Args:
        message: Original message.
        priority: Priority level.
    
    Returns:
        Formatted message with priority prefix.
    """
    priority_prefixes = {
        "critical": ":rotating_light: *CRITICAL*: ",
        "high": ":exclamation: *HIGH*: ",
        "normal": "",
        "low": ":small_blue_diamond: ",
    }
    
    prefix = priority_prefixes.get(priority, "")
    return f"{prefix}{message}"


def _priority_to_color(priority: str) -> str:
    """
    Map priority level to Slack attachment color.
    
    Args:
        priority: Priority level.
    
    Returns:
        Hex color code.
    """
    color_map = {
        "critical": "#dc3545",  # Red
        "high": "#fd7e14",      # Orange
        "normal": "#36a64f",    # Green
        "low": "#6c757d",       # Gray
    }
    return color_map.get(priority, "#36a64f")


def _alert_type_to_priority(alert_type: str) -> str:
    """
    Map alert type to priority level.
    
    Args:
        alert_type: Type of alert.
    
    Returns:
        Priority level string.
    """
    mapping = {
        "error": "critical",
        "warning": "high",
        "info": "normal",
        "success": "low",
    }
    return mapping.get(alert_type, "normal")


def _send_webhook_request(webhook_url: str, payload: dict[str, Any]) -> bool:
    """
    Send HTTP request to Slack webhook.
    
    Args:
        webhook_url: The Slack webhook URL.
        payload: JSON payload to send.
    
    Returns:
        True if request succeeded, False otherwise.
    """
    try:
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        
        with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            if response.status == 200:
                logger.info("Alert sent to Slack successfully")
                return True
            else:
                logger.error(
                    "Slack webhook returned status %d",
                    response.status
                )
                return False
                
    except HTTPError as e:
        logger.error("HTTP error sending Slack alert: %s", e)
        return False
    except URLError as e:
        logger.error("URL error sending Slack alert: %s", e)
        return False
    except TimeoutError:
        logger.error(
            "Timeout sending Slack alert after %d seconds",
            DEFAULT_TIMEOUT_SECONDS
        )
        return False

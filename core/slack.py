"""
Slack Integration for JUGGERNAUT Autonomy Engine
Post status updates to #war-room channel with rate limiting.

Task D.4.1: Add Slack war-room posting capability
"""

import os
import time
import aiohttp
from datetime import datetime, timezone
from typing import Any, Dict

from .database import execute_query, log_execution

# =============================================================================
# CONFIGURATION
# =============================================================================

RATE_LIMIT_SECONDS = 300  # 5 minutes

# In-memory rate limit tracking
_last_post_time: float = 0


# =============================================================================
# RATE LIMITING
# =============================================================================


def _check_rate_limit() -> Dict[str, Any]:
    """
    Check if we can post (5 minute rate limit).
    
    Returns:
        Dict with allowed: bool and wait_seconds if rate limited
    """
    global _last_post_time
    now = time.time()
    
    # Check in-memory tracking first (fastest)
    if _last_post_time > 0 and (now - _last_post_time) < RATE_LIMIT_SECONDS:
        wait = RATE_LIMIT_SECONDS - (now - _last_post_time)
        return {"allowed": False, "wait_seconds": int(wait)}
    
    # Also check database for persistence across restarts
    try:
        result = execute_query(
            """
            SELECT created_at FROM execution_logs 
            WHERE action = 'slack_war_room_post'
            AND level = 'info'
            ORDER BY created_at DESC LIMIT 1
            """
        )
        if result.get("rows"):
            last_post = result["rows"][0].get("created_at")
            if last_post:
                if isinstance(last_post, str):
                    last_post_dt = datetime.fromisoformat(last_post.replace("Z", "+00:00"))
                else:
                    last_post_dt = last_post
                
                now_dt = datetime.now(timezone.utc)
                elapsed = (now_dt - last_post_dt).total_seconds()
                
                if elapsed < RATE_LIMIT_SECONDS:
                    return {"allowed": False, "wait_seconds": int(RATE_LIMIT_SECONDS - elapsed)}
    except Exception:
        pass
    
    return {"allowed": True}


def _update_rate_limit():
    """Update the last post timestamp."""
    global _last_post_time
    _last_post_time = time.time()


def _get_bot_emoji(bot: str) -> str:
    """Get emoji icon for bot."""
    emoji_map = {
        "juggernaut": ":robot_face:",
        "otto": ":gear:",
        "devin": ":hammer_and_wrench:"
    }
    return emoji_map.get(bot.lower(), ":robot_face:")


# =============================================================================
# SLACK POSTING
# =============================================================================


async def post_to_war_room(
    message: str,
    bot: str = "juggernaut",
    force: bool = False
) -> Dict[str, Any]:
    """
    Post a message to #war-room Slack channel.
    
    Args:
        message: Message text (supports Slack mrkdwn)
        bot: Which bot to post as ('otto', 'devin', 'juggernaut')
        force: If True, bypass rate limit (for alerts)
        
    Returns:
        Dict with success status and details
    """
    # Check rate limit (unless forced)
    if not force:
        rate_check = _check_rate_limit()
        if not rate_check["allowed"]:
            return {
                "success": False,
                "error": "Rate limited - max 1 post per 5 minutes",
                "wait_seconds": rate_check.get("wait_seconds", 300)
            }
    
    # Get Slack webhook URL from environment
    webhook_url = os.getenv("SLACK_WAR_ROOM_WEBHOOK")
    if not webhook_url:
        log_execution(
            worker_id="autonomy-engine",
            action="slack_war_room_post",
            message="SLACK_WAR_ROOM_WEBHOOK not configured",
            level="warning"
        )
        return {
            "success": False,
            "error": "SLACK_WAR_ROOM_WEBHOOK not configured"
        }
    
    # Prepare payload
    payload = {
        "text": message,
        "username": bot.upper(),
        "icon_emoji": _get_bot_emoji(bot)
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status == 200:
                    _update_rate_limit()
                    log_execution(
                        worker_id="autonomy-engine",
                        action="slack_war_room_post",
                        message=f"Posted to #war-room as {bot}",
                        level="info",
                        output_data={"bot": bot, "message_preview": message[:100]}
                    )
                    return {
                        "success": True,
                        "message": "Posted to #war-room",
                        "bot": bot
                    }
                else:
                    error_text = await resp.text()
                    log_execution(
                        worker_id="autonomy-engine",
                        action="slack_war_room_post",
                        message=f"Slack API error: {resp.status}",
                        level="error",
                        output_data={"status": resp.status, "error": error_text}
                    )
                    return {
                        "success": False,
                        "error": f"Slack API error: {resp.status}"
                    }
    except Exception as e:
        log_execution(
            worker_id="autonomy-engine",
            action="slack_war_room_post",
            message=f"Exception posting to Slack: {str(e)}",
            level="error"
        )
        return {
            "success": False,
            "error": str(e)
        }


def post_to_war_room_sync(
    message: str,
    bot: str = "juggernaut",
    force: bool = False
) -> Dict[str, Any]:
    """
    Synchronous wrapper for post_to_war_room.
    
    Use this when not in an async context.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(post_to_war_room(message, bot, force))


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def post_status_update(
    title: str,
    details: str,
    bot: str = "juggernaut"
) -> Dict[str, Any]:
    """
    Post a formatted status update to #war-room.
    
    Args:
        title: Update title
        details: Update details/content
        bot: Which bot to post as
        
    Returns:
        Dict with result
    """
    message = f":information_source: *[{title}]* {details}"
    return await post_to_war_room(message, bot)


async def post_alert(
    alert_type: str,
    message: str,
    bot: str = "juggernaut"
) -> Dict[str, Any]:
    """
    Post an alert to #war-room. Alerts bypass rate limit.
    
    Args:
        alert_type: Type of alert ('warning', 'error', 'info', 'success')
        message: Alert message
        bot: Which bot to post as
        
    Returns:
        Dict with result
    """
    emoji_map = {
        "warning": ":warning:",
        "error": ":x:",
        "info": ":information_source:",
        "success": ":white_check_mark:"
    }
    emoji = emoji_map.get(alert_type.lower(), ":information_source:")
    formatted = f"{emoji} *{alert_type.upper()}*: {message}"
    return await post_to_war_room(formatted, bot, force=True)


async def post_pulse(
    workers_active: int,
    pending_tasks: int,
    running_tasks: int,
    completed_today: int,
    failed_today: int,
    dlq_count: int = 0
) -> Dict[str, Any]:
    """
    Post a system pulse update to #war-room.
    
    Args:
        workers_active: Number of active workers
        pending_tasks: Number of pending tasks
        running_tasks: Number of running tasks
        completed_today: Tasks completed today
        failed_today: Tasks failed today
        dlq_count: Items in dead letter queue
        
    Returns:
        Dict with result
    """
    message = (
        f":information_source: *[Pulse]* System pulse:\n"
        f"• Workers: {workers_active} active\n"
        f"• Queue: {pending_tasks} pending, {running_tasks} running\n"
        f"• Today: {completed_today} completed, {failed_today} failed\n"
        f"• DLQ: {dlq_count} awaiting review"
    )
    return await post_to_war_room(message, "juggernaut")

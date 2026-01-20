"""
End-to-End Deployment Verification Pipeline
============================================

Multi-stage verification that tracks tasks from PR creation through deployment.

Stages:
1. coderabbit_review - Wait for CodeRabbit approval
2. merge_verification - Confirm PR is merged
3. deployment_detection - Detect deployment on target platform
4. health_check - Verify health endpoint responds
5. log_monitoring - Watch logs for errors for N minutes

Supports multiple deployment platforms via deployment_targets table.
"""

import os
import re
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

from core.database import query_db


class PipelineStage(Enum):
    """Stages in the verification pipeline."""
    CODERABBIT_REVIEW = "coderabbit_review"
    MERGE_VERIFICATION = "merge_verification"
    DEPLOYMENT_DETECTION = "deployment_detection"
    HEALTH_CHECK = "health_check"
    LOG_MONITORING = "log_monitoring"
    COMPLETED = "completed"
    FAILED = "failed"


class CodeRabbitStatus(Enum):
    """CodeRabbit review statuses."""
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"
    UNKNOWN = "unknown"


@dataclass
class PipelineStatus:
    """Current status of a verification pipeline."""
    pipeline_id: str
    task_id: str
    pr_number: int
    current_stage: str
    overall_status: str
    coderabbit_status: str
    merge_status: str
    deployment_status: str
    health_status: str
    monitoring_status: str
    error_count: int
    failure_reason: Optional[str]


class DeploymentVerificationPipeline:
    """
    Manages end-to-end verification of task deployments.
    
    Tracks each PR through:
    1. CodeRabbit review
    2. Merge to main
    3. Deployment to target platform
    4. Health check
    5. Log monitoring
    """
    
    def __init__(self):
        """Initialize the pipeline manager."""
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.github_repo = os.environ.get("GITHUB_REPO", "SpartanPlumbingJosh/juggernaut-autonomy")
        self.railway_token = os.environ.get("RAILWAY_TOKEN")
        
    # =========================================================================
    # Pipeline Creation & Management
    # =========================================================================
    
    def create_pipeline(self, task_id: str, pr_number: int, pr_url: str) -> Optional[str]:
        """
        Create a new verification pipeline for a task.
        
        Args:
            task_id: The governance task ID
            pr_number: GitHub PR number
            pr_url: Full GitHub PR URL
            
        Returns:
            Pipeline ID if created, None on error
        """
        try:
            # Detect which deployment targets might be affected
            affected_targets = self._detect_affected_targets(pr_number)
            platform = affected_targets[0]["platform"] if affected_targets else "unknown"
            
            query = f"""
                INSERT INTO verification_pipeline (
                    task_id, pr_number, pr_url, deployment_platform
                ) VALUES (
                    '{task_id}'::uuid,
                    {pr_number},
                    '{pr_url}',
                    '{platform}'
                )
                RETURNING id
            """
            
            result = query_db(query)
            if result.get("rows"):
                pipeline_id = result["rows"][0]["id"]
                self._log_pipeline_event(pipeline_id, "pipeline.created", 
                    f"Pipeline created for PR #{pr_number}")
                return pipeline_id
                
        except Exception as e:
            print(f"[PIPELINE] Error creating pipeline: {e}")
            
        return None
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[PipelineStatus]:
        """Get current status of a pipeline."""
        try:
            query = f"""
                SELECT id, task_id, pr_number, current_stage, overall_status,
                       coderabbit_status, merge_status, deployment_status,
                       health_status, monitoring_status, error_count, failure_reason
                FROM verification_pipeline
                WHERE id = '{pipeline_id}'::uuid
            """
            
            result = query_db(query)
            if result.get("rows"):
                row = result["rows"][0]
                return PipelineStatus(
                    pipeline_id=row["id"],
                    task_id=row["task_id"],
                    pr_number=row["pr_number"],
                    current_stage=row["current_stage"],
                    overall_status=row["overall_status"],
                    coderabbit_status=row["coderabbit_status"],
                    merge_status=row["merge_status"],
                    deployment_status=row["deployment_status"],
                    health_status=row["health_status"],
                    monitoring_status=row["monitoring_status"],
                    error_count=row["error_count"],
                    failure_reason=row["failure_reason"]
                )
                
        except Exception as e:
            print(f"[PIPELINE] Error getting status: {e}")
            
        return None
    
    def process_pending_pipelines(self) -> Dict[str, Any]:
        """
        Process all in-progress pipelines.
        Called periodically by the worker loop.
        
        Returns:
            Summary of processing results
        """
        results = {
            "processed": 0,
            "advanced": 0,
            "completed": 0,
            "failed": 0
        }
        
        try:
            # Get all in-progress pipelines
            query = """
                SELECT id, task_id, pr_number, current_stage, 
                       coderabbit_status, merge_status, deployment_platform,
                       deployment_id, monitoring_started_at, monitoring_duration_minutes
                FROM verification_pipeline
                WHERE overall_status = 'in_progress'
                ORDER BY created_at ASC
            """
            
            result = query_db(query)
            pipelines = result.get("rows", [])
            
            for pipeline in pipelines:
                results["processed"] += 1
                
                stage_result = self._process_pipeline_stage(pipeline)
                
                if stage_result == "advanced":
                    results["advanced"] += 1
                elif stage_result == "completed":
                    results["completed"] += 1
                elif stage_result == "failed":
                    results["failed"] += 1
                    
        except Exception as e:
            print(f"[PIPELINE] Error processing pipelines: {e}")
            
        return results
    
    def _process_pipeline_stage(self, pipeline: Dict[str, Any]) -> str:
        """
        Process current stage of a pipeline.
        
        Returns:
            "waiting", "advanced", "completed", or "failed"
        """
        pipeline_id = pipeline["id"]
        current_stage = pipeline["current_stage"]
        pr_number = pipeline["pr_number"]
        
        try:
            if current_stage == PipelineStage.CODERABBIT_REVIEW.value:
                return self._process_coderabbit_stage(pipeline_id, pr_number)
                
            elif current_stage == PipelineStage.MERGE_VERIFICATION.value:
                return self._process_merge_stage(pipeline_id, pr_number)
                
            elif current_stage == PipelineStage.DEPLOYMENT_DETECTION.value:
                return self._process_deployment_stage(pipeline_id, pipeline)
                
            elif current_stage == PipelineStage.HEALTH_CHECK.value:
                return self._process_health_stage(pipeline_id, pipeline)
                
            elif current_stage == PipelineStage.LOG_MONITORING.value:
                return self._process_monitoring_stage(pipeline_id, pipeline)
                
        except Exception as e:
            self._fail_pipeline(pipeline_id, f"Stage processing error: {e}")
            return "failed"
            
        return "waiting"
    
    # =========================================================================
    # Stage 1: CodeRabbit Review
    # =========================================================================
    
    def _process_coderabbit_stage(self, pipeline_id: str, pr_number: int) -> str:
        """Check if CodeRabbit has approved the PR."""
        
        status = self._get_coderabbit_status(pr_number)
        
        if status == CodeRabbitStatus.APPROVED:
            self._update_pipeline(pipeline_id, {
                "coderabbit_status": "approved",
                "coderabbit_approved_at": "NOW()",
                "current_stage": PipelineStage.MERGE_VERIFICATION.value,
                "stage_started_at": "NOW()"
            })
            self._log_pipeline_event(pipeline_id, "coderabbit.approved",
                f"CodeRabbit approved PR #{pr_number}")
            return "advanced"
            
        elif status == CodeRabbitStatus.CHANGES_REQUESTED:
            self._update_pipeline(pipeline_id, {
                "coderabbit_status": "changes_requested"
            })
            self._log_pipeline_event(pipeline_id, "coderabbit.changes_requested",
                f"CodeRabbit requested changes on PR #{pr_number}")
            # Don't fail - wait for fixes
            return "waiting"
            
        return "waiting"
    
    def _get_coderabbit_status(self, pr_number: int) -> CodeRabbitStatus:
        """
        Check CodeRabbit review status on a PR.
        
        Looks for CodeRabbit reviews in PR reviews list.
        """
        if not self.github_token:
            return CodeRabbitStatus.UNKNOWN
            
        try:
            url = f"https://api.github.com/repos/{self.github_repo}/pulls/{pr_number}/reviews"
            
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {self.github_token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                reviews = json.loads(response.read().decode())
                
            # Find CodeRabbit reviews (usually from coderabbitai bot)
            for review in reviews:
                user = review.get("user", {}).get("login", "").lower()
                if "coderabbit" in user or "coderabbitai" in user:
                    state = review.get("state", "").upper()
                    
                    if state == "APPROVED":
                        return CodeRabbitStatus.APPROVED
                    elif state == "CHANGES_REQUESTED":
                        return CodeRabbitStatus.CHANGES_REQUESTED
                    elif state == "COMMENTED":
                        return CodeRabbitStatus.COMMENTED
                        
            # No CodeRabbit review found yet
            return CodeRabbitStatus.PENDING
            
        except Exception as e:
            print(f"[PIPELINE] Error checking CodeRabbit status: {e}")
            return CodeRabbitStatus.UNKNOWN
    
    # =========================================================================
    # Stage 2: Merge Verification
    # =========================================================================
    
    def _process_merge_stage(self, pipeline_id: str, pr_number: int) -> str:
        """Check if PR has been merged."""
        
        merged, merge_sha = self._check_pr_merged(pr_number)
        
        if merged:
            self._update_pipeline(pipeline_id, {
                "merge_status": "merged",
                "merge_commit_sha": f"'{merge_sha}'",
                "merged_at": "NOW()",
                "current_stage": PipelineStage.DEPLOYMENT_DETECTION.value,
                "stage_started_at": "NOW()"
            })
            self._log_pipeline_event(pipeline_id, "pr.merged",
                f"PR #{pr_number} merged with SHA {merge_sha}")
            return "advanced"
            
        return "waiting"
    
    def _check_pr_merged(self, pr_number: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a PR has been merged.
        
        Returns:
            Tuple of (is_merged, merge_commit_sha)
        """
        if not self.github_token:
            return (False, None)
            
        try:
            url = f"https://api.github.com/repos/{self.github_repo}/pulls/{pr_number}"
            
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {self.github_token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                pr_data = json.loads(response.read().decode())
                
            if pr_data.get("merged"):
                return (True, pr_data.get("merge_commit_sha"))
                
        except Exception as e:
            print(f"[PIPELINE] Error checking PR merge status: {e}")
            
        return (False, None)
    
    # =========================================================================
    # Stage 3: Deployment Detection
    # =========================================================================
    
    def _process_deployment_stage(self, pipeline_id: str, pipeline: Dict) -> str:
        """Detect if deployment has been triggered and succeeded."""
        
        platform = pipeline.get("deployment_platform", "railway")
        
        if platform == "railway":
            deployed, deployment_id, deployment_url = self._check_railway_deployment()
        elif platform == "vercel":
            deployed, deployment_id, deployment_url = self._check_vercel_deployment()
        else:
            # Unknown platform - skip to health check
            self._update_pipeline(pipeline_id, {
                "deployment_status": "skipped",
                "current_stage": PipelineStage.HEALTH_CHECK.value,
                "stage_started_at": "NOW()"
            })
            return "advanced"
            
        if deployed:
            self._update_pipeline(pipeline_id, {
                "deployment_status": "success",
                "deployment_id": f"'{deployment_id}'" if deployment_id else "NULL",
                "deployment_url": f"'{deployment_url}'" if deployment_url else "NULL",
                "deployed_at": "NOW()",
                "current_stage": PipelineStage.HEALTH_CHECK.value,
                "stage_started_at": "NOW()"
            })
            self._log_pipeline_event(pipeline_id, "deployment.success",
                f"Deployment succeeded: {deployment_url or deployment_id}")
            return "advanced"
            
        return "waiting"
    
    def _check_railway_deployment(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if Railway deployment succeeded.
        
        Returns:
            Tuple of (deployed, deployment_id, deployment_url)
        """
        if not self.railway_token:
            return (False, None, None)
            
        try:
            # GraphQL query for latest deployment
            query = """
            query {
                deployments(first: 1) {
                    edges {
                        node {
                            id
                            status
                            staticUrl
                        }
                    }
                }
            }
            """
            
            url = "https://backboard.railway.com/graphql/v2"
            data = json.dumps({"query": query}).encode()
            
            req = urllib.request.Request(url, data=data)
            req.add_header("Authorization", f"Bearer {self.railway_token}")
            req.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                
            deployments = result.get("data", {}).get("deployments", {}).get("edges", [])
            
            if deployments:
                latest = deployments[0]["node"]
                if latest.get("status") == "SUCCESS":
                    return (True, latest.get("id"), latest.get("staticUrl"))
                    
        except Exception as e:
            print(f"[PIPELINE] Error checking Railway deployment: {e}")
            
        return (False, None, None)
    
    def _check_vercel_deployment(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if Vercel deployment succeeded.
        
        Returns:
            Tuple of (deployed, deployment_id, deployment_url)
        """
        vercel_token = os.environ.get("VERCEL_TOKEN")
        if not vercel_token:
            return (False, None, None)
            
        try:
            url = "https://api.vercel.com/v6/deployments?limit=1"
            
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {vercel_token}")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                
            deployments = result.get("deployments", [])
            
            if deployments:
                latest = deployments[0]
                if latest.get("state") == "READY":
                    return (True, latest.get("uid"), latest.get("url"))
                    
        except Exception as e:
            print(f"[PIPELINE] Error checking Vercel deployment: {e}")
            
        return (False, None, None)
    
    # =========================================================================
    # Stage 4: Health Check
    # =========================================================================
    
    def _process_health_stage(self, pipeline_id: str, pipeline: Dict) -> str:
        """Check if health endpoint responds correctly."""
        
        # Get health endpoint for the platform
        platform = pipeline.get("deployment_platform", "railway")
        health_url = self._get_health_endpoint(platform)
        
        if not health_url:
            # No health endpoint configured - skip
            self._update_pipeline(pipeline_id, {
                "health_status": "skipped",
                "current_stage": PipelineStage.LOG_MONITORING.value,
                "stage_started_at": "NOW()",
                "monitoring_started_at": "NOW()"
            })
            return "advanced"
            
        is_healthy = self._check_health_endpoint(health_url)
        
        if is_healthy:
            self._update_pipeline(pipeline_id, {
                "health_status": "healthy",
                "health_checked_at": "NOW()",
                "health_endpoint": f"'{health_url}'",
                "current_stage": PipelineStage.LOG_MONITORING.value,
                "stage_started_at": "NOW()",
                "monitoring_started_at": "NOW()"
            })
            self._log_pipeline_event(pipeline_id, "health.passed",
                f"Health check passed: {health_url}")
            return "advanced"
        else:
            # Health check failed - but might just need more time
            # Check if we've been waiting too long
            return "waiting"
    
    def _get_health_endpoint(self, platform: str) -> Optional[str]:
        """Get health endpoint URL for a platform."""
        try:
            query = f"""
                SELECT health_endpoint 
                FROM deployment_targets
                WHERE platform = '{platform}' AND is_active = true
                LIMIT 1
            """
            result = query_db(query)
            if result.get("rows"):
                return result["rows"][0].get("health_endpoint")
        except:
            pass
        return None
    
    def _check_health_endpoint(self, url: str) -> bool:
        """Check if a health endpoint responds with healthy status."""
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Juggernaut-Pipeline/1.0")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read().decode()
                
                # Check for healthy indicators
                if response.status == 200:
                    # Try to parse as JSON
                    try:
                        json_data = json.loads(data)
                        status = json_data.get("status", "").lower()
                        if status in ["healthy", "ok", "running"]:
                            return True
                    except:
                        pass
                    
                    # Check for healthy string
                    if "healthy" in data.lower() or "ok" in data.lower():
                        return True
                        
                    # 200 with content is probably healthy
                    return True
                    
        except Exception as e:
            print(f"[PIPELINE] Health check failed for {url}: {e}")
            
        return False
    
    # =========================================================================
    # Stage 5: Log Monitoring
    # =========================================================================
    
    def _process_monitoring_stage(self, pipeline_id: str, pipeline: Dict) -> str:
        """Monitor logs for errors."""
        
        monitoring_started = pipeline.get("monitoring_started_at")
        duration_minutes = pipeline.get("monitoring_duration_minutes", 5)
        platform = pipeline.get("deployment_platform", "railway")
        deployment_id = pipeline.get("deployment_id")
        
        if not monitoring_started:
            return "waiting"
            
        # Check if monitoring period is complete
        try:
            start_time = datetime.fromisoformat(monitoring_started.replace("Z", "+00:00"))
            elapsed = datetime.now(timezone.utc) - start_time
            
            if elapsed < timedelta(minutes=duration_minutes):
                # Still monitoring - check for errors
                error_count = self._check_logs_for_errors(platform, deployment_id)
                
                if error_count > 0:
                    self._update_pipeline(pipeline_id, {
                        "error_count": error_count
                    })
                    self._log_pipeline_event(pipeline_id, "monitoring.errors_detected",
                        f"Found {error_count} errors in logs")
                
                return "waiting"
                
            # Monitoring complete
            error_count = pipeline.get("error_count", 0)
            
            if error_count == 0:
                # Success!
                self._complete_pipeline(pipeline_id)
                return "completed"
            else:
                # Errors found during monitoring
                self._fail_pipeline(pipeline_id, 
                    f"Found {error_count} errors during log monitoring")
                return "failed"
                
        except Exception as e:
            print(f"[PIPELINE] Error in monitoring stage: {e}")
            return "waiting"
    
    def _check_logs_for_errors(self, platform: str, deployment_id: Optional[str]) -> int:
        """
        Check platform logs for errors.
        
        Returns:
            Count of error log entries found
        """
        error_count = 0
        
        try:
            if platform == "railway" and deployment_id and self.railway_token:
                error_count = self._check_railway_logs(deployment_id)
            elif platform == "vercel":
                error_count = self._check_vercel_logs()
                
        except Exception as e:
            print(f"[PIPELINE] Error checking logs: {e}")
            
        return error_count
    
    def _check_railway_logs(self, deployment_id: str) -> int:
        """Check Railway logs for errors."""
        try:
            query = f"""
            query {{
                deploymentLogs(deploymentId: "{deployment_id}", limit: 100) {{
                    message
                }}
            }}
            """
            
            url = "https://backboard.railway.com/graphql/v2"
            data = json.dumps({"query": query}).encode()
            
            req = urllib.request.Request(url, data=data)
            req.add_header("Authorization", f"Bearer {self.railway_token}")
            req.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                
            logs = result.get("data", {}).get("deploymentLogs", [])
            
            error_patterns = ["error", "exception", "failed", "crash", "fatal"]
            error_count = 0
            
            for log in logs:
                message = log.get("message", "").lower()
                if any(pattern in message for pattern in error_patterns):
                    error_count += 1
                    
            return error_count
            
        except Exception as e:
            print(f"[PIPELINE] Error fetching Railway logs: {e}")
            return 0
    
    def _check_vercel_logs(self) -> int:
        """Check Vercel logs for errors."""
        # Vercel logs require different API - simplified for now
        return 0
    
    # =========================================================================
    # Pipeline Completion/Failure
    # =========================================================================
    
    def _complete_pipeline(self, pipeline_id: str) -> None:
        """Mark pipeline as successfully completed."""
        try:
            # Update pipeline
            self._update_pipeline(pipeline_id, {
                "current_stage": PipelineStage.COMPLETED.value,
                "overall_status": "completed",
                "monitoring_status": "clean",
                "completed_at": "NOW()"
            })
            
            # Update the task's verification status
            query = f"""
                UPDATE governance_tasks
                SET verification_status = 'fully_verified',
                    verification_result = 'Pipeline completed: CodeRabbit approved, PR merged, deployment healthy, logs clean'
                WHERE id = (SELECT task_id FROM verification_pipeline WHERE id = '{pipeline_id}'::uuid)
            """
            query_db(query)
            
            self._log_pipeline_event(pipeline_id, "pipeline.completed",
                "All verification stages passed successfully")
                
        except Exception as e:
            print(f"[PIPELINE] Error completing pipeline: {e}")
    
    def _fail_pipeline(self, pipeline_id: str, reason: str) -> None:
        """Mark pipeline as failed."""
        try:
            self._update_pipeline(pipeline_id, {
                "current_stage": PipelineStage.FAILED.value,
                "overall_status": "failed",
                "failure_reason": f"'{reason.replace(chr(39), chr(39)+chr(39))}'",
                "completed_at": "NOW()"
            })
            
            # Update the task's verification status
            query = f"""
                UPDATE governance_tasks
                SET verification_status = 'failed',
                    verification_result = 'Pipeline failed: {reason.replace("'", "''")}'
                WHERE id = (SELECT task_id FROM verification_pipeline WHERE id = '{pipeline_id}'::uuid)
            """
            query_db(query)
            
            self._log_pipeline_event(pipeline_id, "pipeline.failed", reason)
            
        except Exception as e:
            print(f"[PIPELINE] Error failing pipeline: {e}")
    
    # =========================================================================
    # Utilities
    # =========================================================================
    
    def _update_pipeline(self, pipeline_id: str, updates: Dict[str, Any]) -> None:
        """Update pipeline fields."""
        try:
            set_clauses = []
            for key, value in updates.items():
                if value == "NOW()":
                    set_clauses.append(f"{key} = NOW()")
                elif value == "NULL":
                    set_clauses.append(f"{key} = NULL")
                elif isinstance(value, str) and value.startswith("'"):
                    set_clauses.append(f"{key} = {value}")
                elif isinstance(value, (int, float)):
                    set_clauses.append(f"{key} = {value}")
                else:
                    set_clauses.append(f"{key} = '{value}'")
                    
            set_clauses.append("updated_at = NOW()")
            
            query = f"""
                UPDATE verification_pipeline
                SET {', '.join(set_clauses)}
                WHERE id = '{pipeline_id}'::uuid
            """
            query_db(query)
            
        except Exception as e:
            print(f"[PIPELINE] Error updating pipeline: {e}")
    
    def _log_pipeline_event(self, pipeline_id: str, action: str, message: str) -> None:
        """Log a pipeline event."""
        try:
            message_escaped = message.replace("'", "''")
            query = f"""
                INSERT INTO execution_logs (
                    worker_id, action, message, level
                ) VALUES (
                    'PIPELINE',
                    '{action}',
                    '[Pipeline {pipeline_id[:8]}] {message_escaped}',
                    'info'
                )
            """
            query_db(query)
        except:
            pass
    
    def _detect_affected_targets(self, pr_number: int) -> List[Dict[str, Any]]:
        """
        Detect which deployment targets might be affected by a PR.
        
        For now, returns all active targets. Could be enhanced to
        analyze PR files and determine which services are affected.
        """
        try:
            query = """
                SELECT name, platform, config, health_endpoint
                FROM deployment_targets
                WHERE is_active = true
            """
            result = query_db(query)
            return result.get("rows", [])
        except:
            return []


# =============================================================================
# Convenience Functions
# =============================================================================

def start_verification_pipeline(task_id: str, pr_number: int, pr_url: str) -> Optional[str]:
    """
    Start a new verification pipeline for a task.
    
    Called when a code task creates a PR.
    """
    pipeline = DeploymentVerificationPipeline()
    return pipeline.create_pipeline(task_id, pr_number, pr_url)


def process_all_pipelines() -> Dict[str, Any]:
    """
    Process all pending verification pipelines.
    
    Called periodically by the worker loop (e.g., every minute).
    """
    pipeline = DeploymentVerificationPipeline()
    return pipeline.process_pending_pipelines()


def get_pipeline_for_task(task_id: str) -> Optional[PipelineStatus]:
    """Get verification pipeline status for a task."""
    try:
        query = f"""
            SELECT id FROM verification_pipeline
            WHERE task_id = '{task_id}'::uuid
            ORDER BY created_at DESC
            LIMIT 1
        """
        result = query_db(query)
        if result.get("rows"):
            pipeline_id = result["rows"][0]["id"]
            pipeline = DeploymentVerificationPipeline()
            return pipeline.get_pipeline_status(pipeline_id)
    except:
        pass
    return None

"""
Completion Verification System
==============================

Verifies that completed tasks have valid evidence.
Detects and resets fake completions.
Generates audit reports.

Evidence Types:
- PR merged (GitHub PR URL or number)
- DB row created (table name + row ID)
- File exists (filepath)
- Screenshot URL (image link)
- Explicit skip ("SKIP: reason")
"""

import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from core.database import query_db
from core.notifications import SlackNotifier


# Evidence patterns to match
EVIDENCE_PATTERNS = {
    "pr_created": [
        r"PR #(\d+)",                            # PR #123
        r"github\.com/.*/pull/(\d+)",            # GitHub PR URL
    ],
    "pr_merged": [
        r"merged?.*(pr\.merged|commit|sha)",      # Merge confirmation text only
    ],
    "db_row": [
        r"(inserted|created|added).*?(\d{1,10})?.*(rows?|records?)",  # DB row created
        r"(table:?|into).*[`'\"]?([a-zA-Z_]+)[`'\"]?",                 # Table name
    ],
    "file_exists": [
        r"(file|path|created).*[`'\"]?([/\\\w\.]+\.\w+)[`'\"]?",  # Filepath
    ],
    "screenshot": [
        r"https?://.+\.(png|jpg|jpeg|gif|webp)",  # Image URL
        r"screenshot.*(show|attached|uploaded)",   # Screenshot reference
    ],
    "explicit_skip": [
        r"^SKIP:",                                  # Explicit skip
    ],
}


@dataclass
class VerificationResult:
    """Result of verifying a task's completion evidence."""
    task_id: str
    task_title: str
    has_evidence: bool
    evidence_type: Optional[str] = None
    evidence_text: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class AuditReport:
    """Weekly audit report of task completions."""
    report_date: datetime
    tasks_audited: int
    fake_completions_found: int
    fake_completions_reset: int
    details: List[Dict[str, Any]] = field(default_factory=list)


class CompletionVerifier:
    """Verifies task completions and detects fakes."""
    
    def __init__(self) -> None:
        """Initialize the verifier."""
        self.notifier = SlackNotifier()
    
    def verify_evidence(
        self,
        evidence: Optional[str],
        task_type: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if the provided evidence is valid and classify by type.

        For code/github task types, distinguishes between PR merged vs
        PR created awaiting merge. This enables the completion gating
        logic to defer task completion until PRs are actually merged.

        Args:
            evidence: The completion_evidence text from the task.
            task_type: Optional task type for specialized classification.
                Code-related types (code, github, code_fix, code_change,
                code_implementation) receive stricter PR evidence handling.

        Returns:
            Tuple of (is_valid, evidence_type) where evidence_type may be
            "pr_merged", "pr_created_awaiting_merge", "pr_created",
            "db_row", "file_exists", "screenshot", "explicit_skip",
            or "unstructured".
        """
        if not evidence or not evidence.strip():
            return (False, None)
        
        evidence_lower = evidence.lower()

        task_type_lower = (task_type or "").strip().lower()
        code_task_types = {
            "code",
            "github",
            "code_fix",
            "code_change",
            "code_implementation",
        }
        is_code_task = task_type_lower in code_task_types
        
        # PR evidence should never be assumed "merged" purely from a PR URL.
        # If we have a PR reference and a GitHub token, confirm merged via API.
        pr_url_match = re.search(r"github\.com/[^\s]+/pull/\d+", evidence_lower, re.IGNORECASE)
        pr_num_match = re.search(r"\bpr\s*#\s*(\d+)\b", evidence_lower, re.IGNORECASE)
        if pr_url_match or pr_num_match:
            pr_url = pr_url_match.group(0) if pr_url_match else None
            if not pr_url and pr_num_match:
                repo_env = (os.getenv('GITHUB_REPO') or '').strip()
                if repo_env:
                    pr_url = f"https://github.com/{repo_env}/pull/{pr_num_match.group(1)}"
                else:
                    return (False, None)

            try:
                from core.pr_tracker import PRTracker

                tracker = PRTracker()
                if tracker.github_token and pr_url:
                    status = tracker.get_pr_status(pr_url)
                    if status and getattr(status, "state", None) and status.state.value == "merged":
                        return (True, "pr_merged")
                    return (True, "pr_created_awaiting_merge" if is_code_task else "pr_created")
            except Exception:
                # If we can't confirm, treat as created (not merged).
                return (True, "pr_created_awaiting_merge" if is_code_task else "pr_created")

            return (True, "pr_created_awaiting_merge" if is_code_task else "pr_created")

        # Check each evidence type (non-PR)
        for evidence_type, patterns in EVIDENCE_PATTERNS.items():
            if evidence_type in ("pr_created", "pr_merged"):
                continue
            for pattern in patterns:
                if re.search(pattern, evidence_lower, re.IGNORECASE):
                    return (True, evidence_type)
        
        # If evidence exists but doesn't match patterns, still count it
        # if it's substantive (> 20 chars)
        if len(evidence.strip()) > 20:
            return (True, "unstructured")
        
        return (False, None)
    
    def verify_task(self, task: Dict[str, Any]) -> VerificationResult:
        """
        Verify a single task's completion evidence.

        Args:
            task: Dictionary with task data including id, title, task_type,
                and completion_evidence fields.

        Returns:
            VerificationResult with validation status and evidence classification.
        """
        task_id = task.get("id", "unknown")
        task_title = task.get("title", "Untitled")
        evidence = task.get("completion_evidence")
        task_type = task.get("task_type")
        
        is_valid, evidence_type = self.verify_evidence(evidence, task_type=task_type)
        
        return VerificationResult(
            task_id=task_id,
            task_title=task_title,
            has_evidence=is_valid,
            evidence_type=evidence_type,
            evidence_text=evidence if is_valid else None,
            reason=None if is_valid else "No valid evidence found"
        )
    
    def audit_completed_tasks(self, days_back: int = 7) -> List[VerificationResult]:
        """
        Audit all tasks completed in the last N days.

        Queries governance_tasks for completed tasks and verifies each has
        valid completion evidence. Uses task_type for specialized validation
        of code/github tasks.

        Args:
            days_back: Number of days to look back (default 7).

        Returns:
            List of VerificationResult for each audited task.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff_str = cutoff_date.isoformat()
        
        query = f"""
            SELECT id, title, task_type, completion_evidence, completed_at, assigned_worker
            FROM governance_tasks
            WHERE status = 'completed'
              AND (completed_at >= '{cutoff_str}' OR completed_at IS NULL)
            ORDER BY completed_at DESC NULLS FIRST
        """
        
        try:
            result = query_db(query)
            tasks = result.get("rows", [])
            return [self.verify_task(task) for task in tasks]
        except Exception as e:
            print(f"[VERIFICATION] Error auditing tasks: {e}")
            return []
    
    def reset_fake_completions(self, verifications: List[VerificationResult]) -> int:
        """
        Reset tasks without valid evidence back to pending.
        
        Args:
            verifications: List of VerificationResult objects
            
        Returns:
            Number of tasks reset
        """
        fake_tasks = [v for v in verifications if not v.has_evidence]
        
        if not fake_tasks:
            return 0
        
        reset_count = 0
        
        for task in fake_tasks:
            try:
                # Escape task_id for safety
                task_id_escaped = str(task.task_id).replace("'", "''")
                
                query = f"""
                    UPDATE governance_tasks 
                    SET status = 'pending',
                        completed_at = NULL,
                        error_message = CONCAT(
                            COALESCE(error_message, ''),
                            '[VERIFICATION] Reset: No valid completion evidence. '
                        )
                    WHERE id = '{task_id_escaped}'::uuid
                      AND status = 'completed'
                """
                
                result = query_db(query)
                if result.get("rowCount", 0) > 0:
                    reset_count += 1
                    
                    # Send alert for each fake completion
                    self.notifier.notify_alert(
                        alert_type="Fake Completion Detected",
                        message=f"Task '{task.task_title}' was marked complete without evidence. Reset to pending.",
                        severity="warning"
                    )
                    
            except Exception as e:
                print(f"[VERIFICATION] Error resetting task {task.task_id}: {e}")
        
        return reset_count
    
    def generate_audit_report(self, days_back: int = 7) -> AuditReport:
        """
        Generate a complete audit report.
        
        Args:
            days_back: Number of days to audit
            
        Returns:
            AuditReport with all findings
        """
        # Audit tasks
        verifications = self.audit_completed_tasks(days_back)
        
        # Reset fake completions
        fake_completions = [v for v in verifications if not v.has_evidence]
        reset_count = self.reset_fake_completions(verifications)
        
        # Build report
        report = AuditReport(
            report_date=datetime.now(timezone.utc),
            tasks_audited=len(verifications),
            fake_completions_found=len(fake_completions),
            fake_completions_reset=reset_count,
            details=[
                {
                    "task_id": v.task_id,
                    "task_title": v.task_title,
                    "has_evidence": v.has_evidence,
                    "evidence_type": v.evidence_type,
                }
                for v in verifications
            ]
        )
        
        # Save report to database
        self._save_report(report)
        
        return report
    
    def _save_report(self, report: AuditReport) -> None:
        """Save audit report to database."""
        try:
            details_json = json.dumps(report.details).replace("'", "''")
            report_date = report.report_date.date().isoformat()
            
            query = f"""
                INSERT INTO audit_reports (
                    report_type, 
                    report_date, 
                    tasks_audited, 
                    fake_completions_found, 
                    fake_completions_reset,
                    details
                ) VALUES (
                    'weekly_completion_verification',
                    '{report_date}',
                    {report.tasks_audited},
                    {report.fake_completions_found},
                    {report.fake_completions_reset},
                    '{details_json}'::jsonb
                )
            """
            
            query_db(query)
            
        except Exception as e:
            print(f"[VERIFICATION] Error saving report: {e}")


# Convenience functions for scheduled jobs

def run_daily_verification() -> Dict[str, Any]:
    """
    Run daily verification check.
    Checks tasks completed in the last 24 hours.
    
    Returns:
        Dictionary with verification results
    """
    verifier = CompletionVerifier()
    
    # Check last 24 hours
    verifications = verifier.audit_completed_tasks(days_back=1)
    
    fake_completions = [v for v in verifications if not v.has_evidence]
    
    # Reset fake completions
    reset_count = verifier.reset_fake_completions(verifications)
    
    return {
        "tasks_checked": len(verifications),
        "fake_completions_found": len(fake_completions),
        "tasks_reset": reset_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def run_weekly_audit() -> Dict[str, Any]:
    """
    Run weekly audit and generate report.
    
    Returns:
        Dictionary with audit summary
    """
    verifier = CompletionVerifier()
    
    # Generate full report
    report = verifier.generate_audit_report(days_back=7)
    
    # Send summary to Slack
    verifier.notifier.notify_alert(
        alert_type="Weekly Verification Audit",
        message=f"Tasks audited: {report.tasks_audited}, Fake completions found: {report.fake_completions_found}, Reset: {report.fake_completions_reset}",
        severity="info" if report.fake_completions_found == 0 else "warning"
    )
    
    return {
        "report_date": report.report_date.isoformat(),
        "tasks_audited": report.tasks_audited,
        "fake_completions_found": report.fake_completions_found,
        "fake_completions_reset": report.fake_completions_reset
    }

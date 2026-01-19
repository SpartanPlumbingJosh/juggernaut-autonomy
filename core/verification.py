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

from core.database import execute_query
from core.notifications import SlackNotifier


# Evidence patterns to match
EVIDENCE_PATTERNS = {
    "pr_merged": [
        r"PR #(\d+)",                            # PR #123
        r"github\.com/.*/pull/(\d+)",            # GitHub PR URL
        r"merged?.*(pr\.merged|commit|sha)",      # Merge confirmation
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
    
    def verify_evidence(self, evidence: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Check if the provided evidence is valid.
        
        Args:
            evidence: The completion_evidence text from the task
            
        Returns:
            Tuple of (is_valid, evidence_type)
        """
        if not evidence or not evidence.strip():
            return (False, None)
        
        evidence_lower = evidence.lower()
        
        # Check each evidence type
        for evidence_type, patterns in EVIDENCE_PATTERNS.items():
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
            task: Dictionary with task data (id, title, completion_evidence)
            
        Returns:
            VerificationResult
        """
        task_id = task.get("id", "unknown")
        task_title = task.get("title", "Untitled")
        evidence = task.get("completion_evidence")
        
        is_valid, evidence_type = self.verify_evidence(evidence)
        
        return VerificationResult(
            task_id=task_id,
            task_title=task_title,
            has_evidence=is_valid,
            evidence_type=evidence_type,
            evidence_text=evidence if is_valid else None,
            reason=None if is_valid else "No valid evidence found"
        )
    
    async def audit_completed_tasks(self, days_back: int = 7) -> List[VerificationResult]:
        """
        Audit all tasks completed in the last N days.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of VerificationResult for each task
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        query = """
            SELECT id, title, completion_evidence, completed_at, assigned_worker
            FROM governance_tasks
            WHERE status = 'completed'
              AND (completed_at >= %1 OR completed_at IS NULL)
            ORDER BY completed_at DESC NULLS FIRST
        """
        
        try:
            results = await execute_query(query, [cutoff_date.isoformat()])
            return [self.verify_task(task) for task in results]
        except Exception as e:
            print(f"[VERIFICATION] Error auditing tasks: {e}")
            return []
    
    async def reset_fake_completions(self, verifications: List[VerificationResult]) -> int:
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
                query = """
                    UPDATE governance_tasks 
                    SET status = 'pending',
                        completed_at = NULL,
                        error_message = CONCAT(
                            COALESCE(error_message, ''),
                            '[VERIFICATION] Reset: No valid completion evidence. '
                        )
                    WHERE id = %1::uuid
                      AND status = 'completed'
                """
                
                result = await execute_query(query, [task.task_id])
                if result:
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
    
    async def generate_audit_report(self, days_back: int = 7) -> AuditReport:
        """
        Generate a complete audit report.
        
        Args:
            days_back: Number of days to audit
            
        Returns:
            AuditReport with all findings
        """
        # Audit tasks
        verifications = await self.audit_completed_tasks(days_back)
        
        # Reset fake completions
        fake_completions = [v for v in verifications if not v.has_evidence]
        reset_count = await self.reset_fake_completions(verifications)
        
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
        await self._save_report(report)
        
        return report
    
    async def _save_report(self, report: AuditReport) -> None:
        """Save audit report to database."""
        try:
            query = """
                INSERT INTO audit_reports (
                    report_type, 
                    report_date, 
                    tasks_audited, 
                    fake_completions_found, 
                    fake_completions_reset,
                    details
                ) VALUES (
                    'weekly_completion_verification',
                    %1,
                    %2,
                    %3,
                    %4,
                    %5::jsonb
                )
            """
            
            await execute_query(query, [
                report.report_date.date().isoformat(),
                report.tasks_audited,
                report.fake_completions_found,
                report.fake_completions_reset,
                json.dumps(report.details)
            ])
            
        except Exception as e:
            print(f"[VERIFICATION] Error saving report: {e}")


# Convenience functions for scheduled jobs

async def run_daily_verification() -> Dict[str, Any]:
    """
    Run daily verification check.
    Checks tasks completed in the last 24 hours.
    
    Returns:
        Dictionary with verification results
    """
    verifier = CompletionVerifier()
    
    # Check last 24 hours
    verifications = await verifier.audit_completed_tasks(days_back=1)
    
    fake_completions = [v for v in verifications if not v.has_evidence]
    
    # Reset fake completions
    reset_count = await verifier.reset_fake_completions(verifications)
    
    return {
        "tasks_checked": len(verifications),
        "fake_completions_found": len(fake_completions),
        "tasks_reset": reset_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def run_weekly_audit() -> Dict[str, Any]:
    """
    Run weekly audit and generate report.
    
    Returns:
        Dictionary with audit report summary
    """
    verifier = CompletionVerifier()
    report = await verifier.generate_audit_report(days_back=7)
    
    # Send summary to Slack
    notifier = SlackNotifier()
    notifier.notify_alert(
        alert_type="Weekly Audit Report",
        message=(
            f"Audited: {report.tasks_audited} tasks\n"
            f"Fake completions: {report.fake_completions_found}\n"
            f"Tasks reset: {report.fake_completions_reset}"
        ),
        severity="info" if report.fake_completions_found == 0 else "warning"
    )
    
    return {
        "report_date": report.report_date.isoformat(),
        "tasks_audited": report.tasks_audited,
        "fake_completions_found": report.fake_completions_found,
        "fake_completions_reset": report.fake_completions_reset,
    }

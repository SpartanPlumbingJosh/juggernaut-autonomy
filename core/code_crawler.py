"""
Code Crawler Scheduler

Orchestrates code analysis runs and stores results.

Part of Milestone 4: GitHub Code Crawler
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from core.github_client import get_github_client
from core.analyzers.stale_code import get_stale_detector
from core.code_health_scorer import get_health_scorer
from core.database import fetch_all, execute_sql

logger = logging.getLogger(__name__)


class CodeCrawler:
    """Orchestrates code analysis."""
    
    def __init__(self):
        self.github_client = get_github_client()
        self.stale_detector = get_stale_detector()
        self.health_scorer = get_health_scorer()
    
    def create_analysis_run(
        self,
        repository: str,
        branch: str = "main",
        commit_sha: Optional[str] = None
    ) -> Optional[str]:
        """Create a new analysis run record."""
        try:
            query = """
                INSERT INTO code_analysis_runs (
                    repository,
                    branch,
                    commit_sha,
                    started_at,
                    status
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """
            params = (
                repository,
                branch,
                commit_sha,
                datetime.now(timezone.utc).isoformat(),
                'running'
            )
            
            result = fetch_all(query, params)
            return str(result[0]['id']) if result else None
        except Exception as e:
            logger.exception(f"Error creating analysis run: {e}")
            return None
    
    def update_analysis_run(
        self,
        run_id: str,
        status: str,
        health_score: Optional[float] = None,
        findings_count: int = 0,
        prs_created: int = 0,
        tasks_created: int = 0,
        error_message: Optional[str] = None
    ):
        """Update analysis run status."""
        try:
            query = """
                UPDATE code_analysis_runs
                SET 
                    status = %s,
                    completed_at = %s,
                    health_score = %s,
                    findings_count = %s,
                    prs_created = %s,
                    tasks_created = %s,
                    error_message = %s
                WHERE id = %s
            """
            execute_sql(query, (
                status,
                datetime.now(timezone.utc).isoformat(),
                health_score,
                findings_count,
                prs_created,
                tasks_created,
                error_message,
                run_id
            ))
        except Exception as e:
            logger.exception(f"Error updating analysis run: {e}")
    
    def store_finding(self, run_id: str, finding: Dict[str, Any]) -> Optional[str]:
        """Store a code finding."""
        try:
            query = """
                INSERT INTO code_findings (
                    run_id,
                    finding_type,
                    severity,
                    file_path,
                    line_number,
                    description,
                    suggestion,
                    auto_fixable
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            params = (
                run_id,
                finding.get('type'),
                finding.get('severity', 'medium'),
                finding.get('file_path'),
                finding.get('line_number'),
                finding.get('description'),
                finding.get('suggestion'),
                finding.get('auto_fixable', False)
            )
            
            result = fetch_all(query, params)
            return str(result[0]['id']) if result else None
        except Exception as e:
            logger.exception(f"Error storing finding: {e}")
            return None
    
    def analyze_repository(
        self,
        owner: str,
        repo: str,
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Run full code analysis on a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch to analyze
            
        Returns:
            Analysis results
        """
        repository = f"{owner}/{repo}"
        run_id = None
        
        try:
            # Create analysis run
            run_id = self.create_analysis_run(repository, branch)
            if not run_id:
                return {
                    'success': False,
                    'error': 'Failed to create analysis run'
                }
            
            # Get Python files
            logger.info(f"Fetching Python files from {repository}...")
            python_files = self.github_client.list_files_recursive(
                owner, repo, "", branch, ['.py']
            )
            
            logger.info(f"Found {len(python_files)} Python files")
            
            # Fetch file contents
            file_contents = {}
            for file_path in python_files[:50]:  # Limit to 50 files for now
                content = self.github_client.get_file_content(owner, repo, file_path, branch)
                if content:
                    file_contents[file_path] = content
            
            logger.info(f"Fetched {len(file_contents)} file contents")
            
            # Run stale code analysis
            findings = self.stale_detector.analyze_repository(file_contents)
            
            logger.info(f"Found {len(findings)} issues")
            
            # Store findings
            for finding in findings:
                self.store_finding(run_id, finding)
            
            # Calculate health score
            scores = self.health_scorer.calculate_overall_score(run_id, findings)
            
            # Store metrics
            self.health_scorer.store_metrics(run_id, scores)
            
            # Update run status
            self.update_analysis_run(
                run_id,
                'completed',
                scores['overall_score'],
                len(findings),
                0,  # PRs created (not implemented yet)
                0   # Tasks created (not implemented yet)
            )
            
            return {
                'success': True,
                'run_id': run_id,
                'findings_count': len(findings),
                'health_score': scores['overall_score'],
                'scores': scores
            }
            
        except Exception as e:
            logger.exception(f"Error analyzing repository: {e}")
            
            if run_id:
                self.update_analysis_run(
                    run_id,
                    'failed',
                    error_message=str(e)
                )
            
            return {
                'success': False,
                'error': str(e),
                'run_id': run_id
            }


# Singleton instance
_code_crawler = None


def get_code_crawler() -> CodeCrawler:
    """Get or create code crawler singleton."""
    global _code_crawler
    if _code_crawler is None:
        _code_crawler = CodeCrawler()
    return _code_crawler


__all__ = ["CodeCrawler", "get_code_crawler"]

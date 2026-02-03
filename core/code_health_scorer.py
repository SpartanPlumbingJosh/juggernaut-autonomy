"""
Code Health Scorer

Calculates overall code health score based on multiple metrics.

Part of Milestone 4: GitHub Code Crawler
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from core.database import fetch_all

logger = logging.getLogger(__name__)


class CodeHealthScorer:
    """Calculates code health scores."""
    
    def calculate_staleness_score(self, findings: List[Dict[str, Any]]) -> float:
        """
        Calculate staleness score (0-100, higher is better).
        
        Args:
            findings: List of code findings
            
        Returns:
            Score from 0-100
        """
        stale_findings = [
            f for f in findings 
            if f.get('finding_type') in ['unused_import', 'unused_function', 'commented_code']
        ]
        
        if not findings:
            return 100.0
        
        staleness_ratio = len(stale_findings) / len(findings)
        return (1 - staleness_ratio) * 100
    
    def calculate_contract_score(self, run_id: str) -> float:
        """
        Calculate API contract health score (0-100, higher is better).
        
        Args:
            run_id: Analysis run ID
            
        Returns:
            Score from 0-100
        """
        try:
            query = """
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN status = 'mismatch' THEN 1 ELSE 0 END) as mismatches
                FROM api_contracts
            """
            results = fetch_all(query)
            
            if not results or not results[0].get('total'):
                return 100.0
            
            total = int(results[0].get('total', 0))
            mismatches = int(results[0].get('mismatches', 0))
            
            if total == 0:
                return 100.0
            
            mismatch_ratio = mismatches / total
            return (1 - mismatch_ratio) * 100
        except Exception as e:
            logger.exception(f"Error calculating contract score: {e}")
            return 50.0
    
    def calculate_dependency_score(self) -> float:
        """
        Calculate dependency health score (0-100, higher is better).
        
        Returns:
            Score from 0-100
        """
        try:
            query = """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN is_outdated THEN 1 ELSE 0 END) as outdated,
                       SUM(CASE WHEN has_vulnerabilities THEN 1 ELSE 0 END) as vulnerable
                FROM dependency_status
            """
            results = fetch_all(query)
            
            if not results or not results[0].get('total'):
                return 100.0
            
            total = int(results[0].get('total', 0))
            outdated = int(results[0].get('outdated', 0))
            vulnerable = int(results[0].get('vulnerable', 0))
            
            if total == 0:
                return 100.0
            
            # Vulnerabilities are weighted more heavily
            outdated_ratio = outdated / total
            vulnerable_ratio = vulnerable / total
            
            score = (1 - (outdated_ratio * 0.5 + vulnerable_ratio * 0.5)) * 100
            return max(0, score)
        except Exception as e:
            logger.exception(f"Error calculating dependency score: {e}")
            return 50.0
    
    def calculate_overall_score(
        self,
        run_id: str,
        findings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate overall code health score.
        
        Args:
            run_id: Analysis run ID
            findings: List of findings
            
        Returns:
            Dict with overall score and component scores
        """
        staleness_score = self.calculate_staleness_score(findings)
        contract_score = self.calculate_contract_score(run_id)
        dependency_score = self.calculate_dependency_score()
        
        # Weighted average
        overall_score = (
            staleness_score * 0.4 +
            contract_score * 0.3 +
            dependency_score * 0.3
        )
        
        return {
            'overall_score': round(overall_score, 2),
            'staleness_score': round(staleness_score, 2),
            'contract_score': round(contract_score, 2),
            'dependency_score': round(dependency_score, 2),
            'grade': self._score_to_grade(overall_score)
        }
    
    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def store_metrics(self, run_id: str, scores: Dict[str, Any]):
        """Store health metrics in database."""
        from core.database import execute_sql
        
        try:
            for metric_type, score in scores.items():
                if metric_type == 'grade':
                    continue
                
                query = """
                    INSERT INTO code_health_metrics (
                        run_id,
                        metric_type,
                        score,
                        details
                    ) VALUES (%s, %s, %s, %s)
                """
                execute_sql(query, (
                    run_id,
                    metric_type,
                    score,
                    '{}'
                ))
        except Exception as e:
            logger.exception(f"Error storing metrics: {e}")


# Singleton instance
_health_scorer = None


def get_health_scorer() -> CodeHealthScorer:
    """Get or create health scorer singleton."""
    global _health_scorer
    if _health_scorer is None:
        _health_scorer = CodeHealthScorer()
    return _health_scorer


__all__ = ["CodeHealthScorer", "get_health_scorer"]

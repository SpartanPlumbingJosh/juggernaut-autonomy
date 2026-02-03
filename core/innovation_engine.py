"""
Innovation Engine for Autonomous Revenue Generation.

This module implements the innovation and experimentation system that allows
the autonomous agent to discover new revenue opportunities:
- Opportunity discovery and analysis
- Hypothesis generation for new approaches
- Experiment design and validation
- Success pattern recognition
- Revenue stream diversification
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class OpportunityType(Enum):
    """Types of revenue opportunities."""
    FREELANCE_WORK = "freelance_work"
    API_SERVICE = "api_service"
    DATA_ANALYSIS = "data_analysis"
    CONTENT_CREATION = "content_creation"
    AUTOMATION_SERVICE = "automation_service"
    CONSULTING = "consulting"
    AFFILIATE = "affiliate"
    MARKETPLACE = "marketplace"


class ExperimentStatus(Enum):
    """Status of innovation experiments."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Opportunity:
    """A discovered revenue opportunity."""
    opportunity_id: str = field(default_factory=lambda: str(uuid4()))
    type: OpportunityType = OpportunityType.FREELANCE_WORK
    title: str = ""
    description: str = ""
    estimated_revenue_monthly: float = 0.0
    estimated_effort_hours: float = 0.0
    required_capabilities: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def revenue_per_hour(self) -> float:
        """Calculate estimated revenue per hour."""
        if self.estimated_effort_hours == 0:
            return 0.0
        return self.estimated_revenue_monthly / self.estimated_effort_hours


@dataclass
class Hypothesis:
    """A hypothesis about how to generate revenue."""
    hypothesis_id: str = field(default_factory=lambda: str(uuid4()))
    statement: str = ""
    opportunity_id: Optional[str] = None
    expected_outcome: str = ""
    success_criteria: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    estimated_cost_cents: float = 0.0
    estimated_time_days: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Experiment:
    """An experiment to test a hypothesis."""
    experiment_id: str = field(default_factory=lambda: str(uuid4()))
    hypothesis_id: str = ""
    title: str = ""
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    budget_cents: float = 0.0
    spent_cents: float = 0.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)
    success: Optional[bool] = None
    learnings: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InnovationEngine:
    """
    Drives innovation and experimentation for revenue generation.
    
    Responsibilities:
    - Discover new revenue opportunities
    - Generate hypotheses for testing
    - Design and run experiments
    - Learn from successes and failures
    - Optimize revenue strategies
    """
    
    def __init__(self):
        """Initialize innovation engine."""
        self.opportunities: Dict[str, Opportunity] = {}
        self.hypotheses: Dict[str, Hypothesis] = {}
        self.experiments: Dict[str, Experiment] = {}
        self.success_patterns: List[Dict[str, Any]] = []
        self.total_revenue_generated: float = 0.0
        
        logger.info("Innovation engine initialized")
    
    def discover_opportunity(
        self,
        type: OpportunityType,
        title: str,
        description: str,
        estimated_revenue: float,
        estimated_effort: float,
        required_capabilities: List[str],
        confidence: float,
        source: str = "manual"
    ) -> Opportunity:
        """
        Register a discovered revenue opportunity.
        
        Args:
            type: Type of opportunity
            title: Opportunity title
            description: Detailed description
            estimated_revenue: Monthly revenue estimate
            estimated_effort: Hours of effort required
            required_capabilities: Capabilities needed
            confidence: Confidence score (0-1)
            source: How opportunity was discovered
            
        Returns:
            Created Opportunity
        """
        opportunity = Opportunity(
            type=type,
            title=title,
            description=description,
            estimated_revenue_monthly=estimated_revenue,
            estimated_effort_hours=estimated_effort,
            required_capabilities=required_capabilities,
            confidence_score=confidence,
            source=source,
        )
        
        self.opportunities[opportunity.opportunity_id] = opportunity
        
        logger.info(
            f"Discovered opportunity: {title} "
            f"(${estimated_revenue:.2f}/mo, {estimated_effort}h, "
            f"confidence={confidence:.2f})"
        )
        
        return opportunity
    
    def generate_hypothesis(
        self,
        opportunity_id: str,
        statement: str,
        expected_outcome: str,
        success_criteria: List[str],
        risks: List[str],
        estimated_cost: float,
        estimated_time: float
    ) -> Hypothesis:
        """
        Generate a hypothesis for testing an opportunity.
        
        Args:
            opportunity_id: Related opportunity
            statement: Hypothesis statement
            expected_outcome: What we expect to happen
            success_criteria: How we measure success
            risks: Potential risks
            estimated_cost: Cost in cents
            estimated_time: Time in days
            
        Returns:
            Created Hypothesis
        """
        hypothesis = Hypothesis(
            opportunity_id=opportunity_id,
            statement=statement,
            expected_outcome=expected_outcome,
            success_criteria=success_criteria,
            risks=risks,
            estimated_cost_cents=estimated_cost,
            estimated_time_days=estimated_time,
        )
        
        self.hypotheses[hypothesis.hypothesis_id] = hypothesis
        
        logger.info(f"Generated hypothesis: {statement}")
        
        return hypothesis
    
    def create_experiment(
        self,
        hypothesis_id: str,
        title: str,
        description: str,
        budget_cents: float
    ) -> Experiment:
        """
        Create an experiment to test a hypothesis.
        
        Args:
            hypothesis_id: Hypothesis to test
            title: Experiment title
            description: Experiment description
            budget_cents: Budget in cents
            
        Returns:
            Created Experiment
        """
        experiment = Experiment(
            hypothesis_id=hypothesis_id,
            title=title,
            description=description,
            budget_cents=budget_cents,
        )
        
        self.experiments[experiment.experiment_id] = experiment
        
        logger.info(f"Created experiment: {title} (budget=${budget_cents/100:.2f})")
        
        return experiment
    
    def start_experiment(self, experiment_id: str) -> bool:
        """
        Start running an experiment.
        
        Args:
            experiment_id: Experiment to start
            
        Returns:
            True if started successfully
        """
        if experiment_id not in self.experiments:
            return False
        
        experiment = self.experiments[experiment_id]
        
        if experiment.status != ExperimentStatus.PROPOSED:
            logger.warning(f"Experiment {experiment_id} not in proposed state")
            return False
        
        experiment.status = ExperimentStatus.RUNNING
        experiment.start_date = datetime.now(timezone.utc)
        
        logger.info(f"Started experiment: {experiment.title}")
        
        return True
    
    def complete_experiment(
        self,
        experiment_id: str,
        success: bool,
        results: Dict[str, Any],
        learnings: List[str],
        spent_cents: float
    ) -> bool:
        """
        Mark experiment as completed with results.
        
        Args:
            experiment_id: Experiment to complete
            success: Whether experiment succeeded
            results: Experiment results
            learnings: Key learnings
            spent_cents: Actual cost
            
        Returns:
            True if completed successfully
        """
        if experiment_id not in self.experiments:
            return False
        
        experiment = self.experiments[experiment_id]
        
        experiment.status = ExperimentStatus.COMPLETED if success else ExperimentStatus.FAILED
        experiment.end_date = datetime.now(timezone.utc)
        experiment.success = success
        experiment.results = results
        experiment.learnings = learnings
        experiment.spent_cents = spent_cents
        
        # Extract success patterns
        if success:
            self._extract_success_pattern(experiment)
        
        logger.info(
            f"Completed experiment: {experiment.title} "
            f"(success={success}, spent=${spent_cents/100:.2f})"
        )
        
        return True
    
    def _extract_success_pattern(self, experiment: Experiment) -> None:
        """Extract patterns from successful experiments."""
        hypothesis = self.hypotheses.get(experiment.hypothesis_id)
        
        if not hypothesis:
            return
        
        opportunity = None
        if hypothesis.opportunity_id:
            opportunity = self.opportunities.get(hypothesis.opportunity_id)
        
        pattern = {
            "experiment_id": experiment.experiment_id,
            "opportunity_type": opportunity.type.value if opportunity else "unknown",
            "hypothesis": hypothesis.statement,
            "success_criteria": hypothesis.success_criteria,
            "results": experiment.results,
            "learnings": experiment.learnings,
            "roi": self._calculate_roi(experiment),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.success_patterns.append(pattern)
        
        logger.info(f"Extracted success pattern from experiment {experiment.experiment_id}")
    
    def _calculate_roi(self, experiment: Experiment) -> float:
        """Calculate ROI for an experiment."""
        revenue = experiment.results.get("revenue_generated", 0.0)
        cost = experiment.spent_cents
        
        if cost == 0:
            return 0.0
        
        return ((revenue - cost) / cost) * 100
    
    def get_top_opportunities(self, limit: int = 10) -> List[Opportunity]:
        """
        Get top opportunities ranked by revenue per hour and confidence.
        
        Args:
            limit: Maximum number to return
            
        Returns:
            List of top opportunities
        """
        opportunities = list(self.opportunities.values())
        
        # Score = revenue_per_hour * confidence
        scored = [
            (opp, opp.revenue_per_hour * opp.confidence_score)
            for opp in opportunities
        ]
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [opp for opp, score in scored[:limit]]
    
    def get_innovation_metrics(self) -> Dict[str, Any]:
        """Get innovation engine metrics."""
        total_experiments = len(self.experiments)
        completed = sum(
            1 for exp in self.experiments.values()
            if exp.status == ExperimentStatus.COMPLETED
        )
        successful = sum(
            1 for exp in self.experiments.values()
            if exp.success is True
        )
        
        success_rate = (successful / completed * 100) if completed > 0 else 0.0
        
        total_spent = sum(exp.spent_cents for exp in self.experiments.values())
        total_revenue = sum(
            exp.results.get("revenue_generated", 0.0)
            for exp in self.experiments.values()
        )
        
        return {
            "total_opportunities": len(self.opportunities),
            "total_hypotheses": len(self.hypotheses),
            "total_experiments": total_experiments,
            "completed_experiments": completed,
            "successful_experiments": successful,
            "success_rate_percent": round(success_rate, 2),
            "total_spent_cents": total_spent,
            "total_revenue_generated": total_revenue,
            "net_profit": total_revenue - total_spent,
            "success_patterns_identified": len(self.success_patterns),
        }


# Global innovation engine instance
_engine: Optional[InnovationEngine] = None


def get_innovation_engine() -> InnovationEngine:
    """Get or create global innovation engine instance."""
    global _engine
    if _engine is None:
        _engine = InnovationEngine()
    return _engine

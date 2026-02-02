"""
Experiment lifecycle management for JUGGERNAUT.

This module provides functions for managing the full lifecycle of experiments,
including state transitions, snapshots, and rollbacks. It ensures that
experiments follow a structured workflow and can be safely rolled back if needed.

Usage:
    from core.lifecycle import ExperimentLifecycle
    
    # Create a lifecycle manager
    lifecycle = ExperimentLifecycle()
    
    # Create a new experiment with hypothesis
    experiment_id = await lifecycle.create_experiment(
        title="Revenue Optimization Test",
        description="Testing price elasticity for checkout flow",
        hypothesis_id="123e4567-e89b-12d3-a456-426614174000"
    )
    
    # Transition experiment through states
    await lifecycle.transition_state(experiment_id, "preparing")
    await lifecycle.transition_state(experiment_id, "running")
    
    # Create a rollback point
    await lifecycle.create_snapshot(experiment_id, "rollback_point")
    
    # Rollback if needed
    await lifecycle.rollback(experiment_id)
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from .database import query_db

logger = logging.getLogger(__name__)

class LifecycleError(Exception):
    """Exception raised for errors in the lifecycle module."""
    pass

class ExperimentLifecycle:
    """Manages the lifecycle of experiments."""
    
    async def create_experiment(
        self,
        title: str,
        description: str,
        experiment_type: str = "revenue",
        hypothesis_id: Optional[str] = None,
        worker_id: str = "ORCHESTRATOR",
        tags: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new experiment with lifecycle management.
        
        Args:
            title: Experiment title
            description: Experiment description
            experiment_type: Type of experiment
            hypothesis_id: Optional ID of associated hypothesis
            worker_id: ID of the worker creating the experiment
            tags: Optional list of tags
            parameters: Optional experiment parameters
            
        Returns:
            ID of the created experiment
            
        Raises:
            LifecycleError: If experiment creation fails
        """
        try:
            # Parse hypothesis_id
            hypothesis_uuid = self._parse_uuid(hypothesis_id)
            
            # Create experiment
            result = await query_db(
                """
                INSERT INTO experiments (
                    title, description, experiment_type,
                    hypothesis_id, created_by, tags, parameters,
                    lifecycle_state, state_last_changed_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, NOW()
                )
                RETURNING id
                """,
                [
                    title, description, experiment_type,
                    hypothesis_uuid, worker_id, tags,
                    json.dumps(parameters) if parameters else "{}",
                    "created"
                ]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                raise LifecycleError("Failed to create experiment")
            
            experiment_id = str(result["rows"][0]["id"])
            
            # Create initial snapshot
            await self.create_snapshot(
                experiment_id=experiment_id,
                snapshot_type="initial",
                notes="Initial experiment state",
                created_by=worker_id
            )
            
            logger.info(f"Created experiment {experiment_id} in 'created' state")
            
            return experiment_id
        except Exception as e:
            logger.error(f"Failed to create experiment: {e}")
            raise LifecycleError(f"Failed to create experiment: {e}")
    
    async def create_hypothesis(
        self,
        title: str,
        description: str,
        expected_outcome: str,
        success_criteria: str,
        category: Optional[str] = None,
        confidence_level: float = 0.5,
        priority: str = "medium",
        worker_id: str = "ORCHESTRATOR",
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Create a new hypothesis for experiments.
        
        Args:
            title: Hypothesis title
            description: Hypothesis description
            expected_outcome: Expected outcome if hypothesis is true
            success_criteria: Criteria to determine if hypothesis is validated
            category: Optional category
            confidence_level: Confidence level (0.0 to 1.0)
            priority: Priority level
            worker_id: ID of the worker creating the hypothesis
            tags: Optional list of tags
            
        Returns:
            ID of the created hypothesis
            
        Raises:
            LifecycleError: If hypothesis creation fails
        """
        try:
            result = await query_db(
                """
                INSERT INTO hypotheses (
                    title, description, expected_outcome,
                    success_criteria, category, confidence_level,
                    priority, created_by, tags
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9
                )
                RETURNING id
                """,
                [
                    title, description, expected_outcome,
                    success_criteria, category, confidence_level,
                    priority, worker_id, tags
                ]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                raise LifecycleError("Failed to create hypothesis")
            
            hypothesis_id = str(result["rows"][0]["id"])
            
            logger.info(f"Created hypothesis {hypothesis_id}")
            
            return hypothesis_id
        except Exception as e:
            logger.error(f"Failed to create hypothesis: {e}")
            raise LifecycleError(f"Failed to create hypothesis: {e}")
    
    async def transition_state(
        self,
        experiment_id: str,
        new_state: str,
        notes: Optional[str] = None,
        actor: str = "system"
    ) -> bool:
        """
        Transition an experiment to a new state.
        
        Valid state transitions:
        - created -> preparing -> running -> evaluating -> completed
        - preparing/running/evaluating -> failed
        - running/evaluating -> rolled_back
        
        Args:
            experiment_id: ID of the experiment
            new_state: New state to transition to
            notes: Optional notes about the transition
            actor: ID of the actor making the transition
            
        Returns:
            True if transition was successful
            
        Raises:
            LifecycleError: If transition fails
        """
        try:
            # Use the database function to transition state
            result = await query_db(
                """
                SELECT transition_experiment_state($1, $2, $3, $4) as success
                """,
                [experiment_id, new_state, notes, actor]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                raise LifecycleError("Failed to transition experiment state")
            
            success = result["rows"][0].get("success", False)
            
            if success:
                logger.info(f"Transitioned experiment {experiment_id} to '{new_state}'")
                
                # Create snapshot for key state transitions
                if new_state in ["running", "evaluating", "completed"]:
                    await self.create_snapshot(
                        experiment_id=experiment_id,
                        snapshot_type=f"state_{new_state}",
                        notes=f"Snapshot at {new_state} state transition",
                        created_by=actor
                    )
            
            return success
        except Exception as e:
            logger.error(f"Failed to transition experiment {experiment_id} to {new_state}: {e}")
            raise LifecycleError(f"Failed to transition state: {e}")
    
    async def create_snapshot(
        self,
        experiment_id: str,
        snapshot_type: str = "manual",
        tables: Optional[List[str]] = None,
        notes: Optional[str] = None,
        created_by: str = "system"
    ) -> str:
        """
        Create a snapshot of experiment state.
        
        Args:
            experiment_id: ID of the experiment
            snapshot_type: Type of snapshot
            tables: Optional list of tables to include
            notes: Optional notes about the snapshot
            created_by: ID of the actor creating the snapshot
            
        Returns:
            ID of the created snapshot
            
        Raises:
            LifecycleError: If snapshot creation fails
        """
        try:
            # Use the database function to create snapshot
            result = await query_db(
                """
                SELECT create_experiment_snapshot($1, $2, $3, $4, $5) as snapshot_id
                """,
                [experiment_id, snapshot_type, tables, notes, created_by]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                raise LifecycleError("Failed to create experiment snapshot")
            
            snapshot_id = str(result["rows"][0].get("snapshot_id"))
            
            logger.info(f"Created {snapshot_type} snapshot {snapshot_id} for experiment {experiment_id}")
            
            return snapshot_id
        except Exception as e:
            logger.error(f"Failed to create snapshot for experiment {experiment_id}: {e}")
            raise LifecycleError(f"Failed to create snapshot: {e}")
    
    async def rollback(
        self,
        experiment_id: str,
        snapshot_id: Optional[str] = None,
        notes: Optional[str] = None,
        actor: str = "system"
    ) -> bool:
        """
        Rollback an experiment to a previous state.
        
        Args:
            experiment_id: ID of the experiment
            snapshot_id: Optional ID of snapshot to rollback to
            notes: Optional notes about the rollback
            actor: ID of the actor performing the rollback
            
        Returns:
            True if rollback was successful
            
        Raises:
            LifecycleError: If rollback fails
        """
        try:
            # Parse snapshot_id
            snapshot_uuid = self._parse_uuid(snapshot_id)
            
            # Use the database function to rollback
            result = await query_db(
                """
                SELECT rollback_experiment($1, $2, $3, $4) as success
                """,
                [experiment_id, snapshot_uuid, actor, notes]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                raise LifecycleError("Failed to rollback experiment")
            
            success = result["rows"][0].get("success", False)
            
            if success:
                logger.info(f"Rolled back experiment {experiment_id}")
            
            return success
        except Exception as e:
            logger.error(f"Failed to rollback experiment {experiment_id}: {e}")
            raise LifecycleError(f"Failed to rollback experiment: {e}")
    
    async def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get experiment details including lifecycle state.
        
        Args:
            experiment_id: ID of the experiment
            
        Returns:
            Experiment data or None if not found
            
        Raises:
            LifecycleError: If retrieval fails
        """
        try:
            result = await query_db(
                """
                SELECT e.*, h.title as hypothesis_title, h.description as hypothesis_description
                FROM experiments e
                LEFT JOIN hypotheses h ON e.hypothesis_id = h.id
                WHERE e.id = $1
                """,
                [experiment_id]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                return None
            
            experiment = result["rows"][0]
            
            # Get state history
            history_result = await query_db(
                """
                SELECT * FROM experiment_state_history
                WHERE experiment_id = $1
                ORDER BY transitioned_at ASC
                """,
                [experiment_id]
            )
            
            experiment["state_history"] = history_result.get("rows", []) if history_result else []
            
            # Get metrics
            metrics_result = await query_db(
                """
                SELECT * FROM experiment_metrics
                WHERE experiment_id = $1
                """,
                [experiment_id]
            )
            
            experiment["metrics"] = metrics_result.get("rows", []) if metrics_result else []
            
            # Get snapshots
            snapshots_result = await query_db(
                """
                SELECT id, snapshot_type, created_at, created_by, notes
                FROM experiment_snapshots
                WHERE experiment_id = $1
                ORDER BY created_at DESC
                """,
                [experiment_id]
            )
            
            experiment["snapshots"] = snapshots_result.get("rows", []) if snapshots_result else []
            
            return experiment
        except Exception as e:
            logger.error(f"Failed to get experiment {experiment_id}: {e}")
            raise LifecycleError(f"Failed to get experiment: {e}")
    
    async def create_metric(
        self,
        experiment_id: str,
        metric_name: str,
        metric_type: str,
        baseline_value: Optional[float] = None,
        target_value: Optional[float] = None,
        unit: Optional[str] = None,
        collection_method: str = "manual",
        collection_query: Optional[str] = None,
        collection_frequency: str = "once"
    ) -> str:
        """
        Create a metric for experiment tracking.
        
        Args:
            experiment_id: ID of the experiment
            metric_name: Name of the metric
            metric_type: Type of metric
            baseline_value: Optional baseline value
            target_value: Optional target value
            unit: Optional unit of measurement
            collection_method: Method of collection
            collection_query: Optional query for automatic collection
            collection_frequency: Frequency of collection
            
        Returns:
            ID of the created metric
            
        Raises:
            LifecycleError: If metric creation fails
        """
        try:
            result = await query_db(
                """
                INSERT INTO experiment_metrics (
                    experiment_id, metric_name, metric_type,
                    baseline_value, target_value, unit,
                    collection_method, collection_query, collection_frequency
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9
                )
                RETURNING id
                """,
                [
                    experiment_id, metric_name, metric_type,
                    baseline_value, target_value, unit,
                    collection_method, collection_query, collection_frequency
                ]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                raise LifecycleError("Failed to create metric")
            
            metric_id = str(result["rows"][0]["id"])
            
            logger.info(f"Created metric {metric_id} for experiment {experiment_id}")
            
            return metric_id
        except Exception as e:
            logger.error(f"Failed to create metric for experiment {experiment_id}: {e}")
            raise LifecycleError(f"Failed to create metric: {e}")
    
    async def update_metric_value(
        self,
        metric_id: str,
        value: float,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update a metric value and record in history.
        
        Args:
            metric_id: ID of the metric
            value: New metric value
            notes: Optional notes about the update
            
        Returns:
            True if update was successful
            
        Raises:
            LifecycleError: If update fails
        """
        try:
            # Update current value
            update_result = await query_db(
                """
                UPDATE experiment_metrics
                SET actual_value = $1,
                    last_collected_at = NOW(),
                    updated_at = NOW()
                WHERE id = $2
                RETURNING id
                """,
                [value, metric_id]
            )
            
            if not update_result or "rows" not in update_result or not update_result["rows"]:
                raise LifecycleError(f"Metric {metric_id} not found")
            
            # Record in history
            history_result = await query_db(
                """
                INSERT INTO experiment_metric_history (
                    metric_id, value, notes
                ) VALUES (
                    $1, $2, $3
                )
                RETURNING id
                """,
                [metric_id, value, notes]
            )
            
            if not history_result or "rows" not in history_result or not history_result["rows"]:
                logger.warning(f"Failed to record metric history for {metric_id}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to update metric {metric_id}: {e}")
            raise LifecycleError(f"Failed to update metric: {e}")
    
    async def get_metrics(
        self,
        experiment_id: str,
        include_history: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get metrics for an experiment.
        
        Args:
            experiment_id: ID of the experiment
            include_history: Whether to include metric history
            
        Returns:
            List of metrics
            
        Raises:
            LifecycleError: If retrieval fails
        """
        try:
            result = await query_db(
                """
                SELECT * FROM experiment_metrics
                WHERE experiment_id = $1
                """,
                [experiment_id]
            )
            
            if not result or "rows" not in result:
                return []
            
            metrics = result["rows"]
            
            if include_history:
                for metric in metrics:
                    metric_id = metric["id"]
                    
                    history_result = await query_db(
                        """
                        SELECT * FROM experiment_metric_history
                        WHERE metric_id = $1
                        ORDER BY collected_at ASC
                        """,
                        [metric_id]
                    )
                    
                    metric["history"] = history_result.get("rows", []) if history_result else []
            
            return metrics
        except Exception as e:
            logger.error(f"Failed to get metrics for experiment {experiment_id}: {e}")
            raise LifecycleError(f"Failed to get metrics: {e}")
    
    def _parse_uuid(self, uuid_str: Optional[str]) -> Optional[uuid.UUID]:
        """
        Parse a UUID string to a UUID object.
        
        Args:
            uuid_str: UUID string or None
            
        Returns:
            UUID object or None
        """
        if not uuid_str:
            return None
        
        try:
            return uuid.UUID(uuid_str)
        except ValueError:
            return None

"""
Auto-scaling module for Juggernaut worker management.

This module monitors task queue depth and automatically scales workers
up or down based on configurable thresholds and policies. Now includes
Railway API integration for spawning real worker containers.
"""

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_MIN_WORKERS = 1
DEFAULT_MAX_WORKERS = 10
SCALE_UP_THRESHOLD = 5
SCALE_DOWN_THRESHOLD = 0
SCALE_UP_COOLDOWN_SECONDS = 300
SCALE_DOWN_COOLDOWN_SECONDS = 600
HEARTBEAT_STALE_SECONDS = 120

# Railway configuration
RAILWAY_API_ENDPOINT = "https://backboard.railway.com/graphql/v2"
RAILWAY_HEALTH_CHECK_RETRIES = 10
RAILWAY_HEALTH_CHECK_INTERVAL_SECONDS = 6
RAILWAY_DEPLOYMENT_TIMEOUT_SECONDS = 180


class ScalingAction(Enum):
    """Types of scaling actions."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


class DeploymentStatus(Enum):
    """Railway deployment statuses."""
    BUILDING = "BUILDING"
    DEPLOYING = "DEPLOYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CRASHED = "CRASHED"
    REMOVED = "REMOVED"


@dataclass
class ScalingConfig:
    """Configuration for auto-scaling behavior."""
    min_workers: int = DEFAULT_MIN_WORKERS
    max_workers: int = DEFAULT_MAX_WORKERS
    scale_up_threshold: int = SCALE_UP_THRESHOLD
    scale_down_threshold: int = SCALE_DOWN_THRESHOLD
    scale_up_cooldown_seconds: int = SCALE_UP_COOLDOWN_SECONDS
    scale_down_cooldown_seconds: int = SCALE_DOWN_COOLDOWN_SECONDS
    enabled: bool = True


@dataclass
class RailwayConfig:
    """Configuration for Railway API integration."""
    api_token: str = ""
    project_id: str = ""
    environment_id: str = ""
    template_service_id: str = ""
    repo_url: str = ""
    branch: str = "main"


@dataclass
class ScalingDecision:
    """Result of a scaling evaluation."""
    action: ScalingAction
    reason: str
    current_workers: int
    current_queue_depth: int
    target_workers: Optional[int] = None
    workers_to_add: int = 0
    workers_to_remove: int = 0


@dataclass
class QueueMetrics:
    """Metrics about the task queue."""
    pending_count: int
    in_progress_count: int
    waiting_approval_count: int
    total_actionable: int


@dataclass
class WorkerMetrics:
    """Metrics about active workers."""
    active_count: int
    idle_count: int
    stale_count: int
    total_capacity: int


@dataclass
class SpawnResult:
    """Result of a worker spawn operation."""
    success: bool
    worker_id: Optional[str] = None
    service_id: Optional[str] = None
    deployment_id: Optional[str] = None
    error: Optional[str] = None
    health_verified: bool = False


class RailwayClient:
    """
    Client for Railway API GraphQL operations.
    
    Handles service creation, deployment, and health monitoring
    for auto-scaled worker containers.
    """
    
    def __init__(self, config: RailwayConfig) -> None:
        """
        Initialize Railway client.
        
        Args:
            config: Railway API configuration
        """
        self.config = config
        self._http_client: Optional[httpx.Client] = None
    
    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=60.0)
        return self._http_client
    
    def _execute_graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query against Railway API.
        
        Args:
            query: GraphQL query or mutation
            variables: Optional query variables
            
        Returns:
            GraphQL response data
            
        Raises:
            RuntimeError: If query execution fails
        """
        try:
            payload: Dict[str, Any] = {"query": query}
            if variables:
                payload["variables"] = variables
            
            response = self.http_client.post(
                RAILWAY_API_ENDPOINT,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_token}"
                },
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if "errors" in result:
                error_msg = result["errors"][0].get("message", "Unknown error")
                logger.error("Railway GraphQL error: %s", error_msg)
                raise RuntimeError(f"Railway API error: {error_msg}")
            
            return result.get("data", {})
            
        except httpx.HTTPError as exc:
            logger.error("Railway API request failed: %s", exc)
            raise RuntimeError(f"Railway API request failed: {exc}") from exc
    
    def create_service(self, worker_name: str) -> Optional[str]:
        """
        Create a new service in the Railway project.
        
        Args:
            worker_name: Name for the new worker service
            
        Returns:
            Service ID if created successfully, None otherwise
        """
        mutation = """
            mutation serviceCreate($input: ServiceCreateInput!) {
                serviceCreate(input: $input) {
                    id
                    name
                }
            }
        """
        
        variables = {
            "input": {
                "projectId": self.config.project_id,
                "name": worker_name
            }
        }
        
        try:
            result = self._execute_graphql(mutation, variables)
            service_data = result.get("serviceCreate", {})
            service_id = service_data.get("id")
            
            if service_id:
                logger.info("Created Railway service: %s (%s)", worker_name, service_id)
                return service_id
            
            logger.error("Failed to create service: no ID returned")
            return None
            
        except RuntimeError as exc:
            logger.error("Failed to create service %s: %s", worker_name, exc)
            return None
    
    def connect_service_to_repo(
        self,
        service_id: str
    ) -> bool:
        """
        Connect a service to the GitHub repository.
        
        Args:
            service_id: ID of the service to connect
            
        Returns:
            True if connected successfully
        """
        mutation = """
            mutation serviceConnect($input: ServiceConnectInput!) {
                serviceConnect(input: $input) {
                    id
                }
            }
        """
        
        variables = {
            "input": {
                "id": service_id,
                "repo": self.config.repo_url,
                "branch": self.config.branch
            }
        }
        
        try:
            self._execute_graphql(mutation, variables)
            logger.info("Connected service %s to repo", service_id)
            return True
        except RuntimeError as exc:
            logger.error("Failed to connect service to repo: %s", exc)
            return False
    
    def trigger_deployment(
        self,
        service_id: str,
        environment_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Trigger a deployment for a service.
        
        Args:
            service_id: ID of the service to deploy
            environment_id: Optional environment ID (uses config default)
            
        Returns:
            Deployment ID if triggered successfully, None otherwise
        """
        env_id = environment_id or self.config.environment_id
        
        mutation = """
            mutation deploymentTriggerCreate($input: DeploymentTriggerCreateInput!) {
                deploymentTriggerCreate(input: $input) {
                    id
                }
            }
        """
        
        variables = {
            "input": {
                "serviceId": service_id,
                "environmentId": env_id
            }
        }
        
        try:
            result = self._execute_graphql(mutation, variables)
            trigger_data = result.get("deploymentTriggerCreate", {})
            deployment_id = trigger_data.get("id")
            
            if deployment_id:
                logger.info("Triggered deployment for service %s", service_id)
                return deployment_id
            
            return None
            
        except RuntimeError as exc:
            logger.error("Failed to trigger deployment: %s", exc)
            return None
    
    def get_deployment_status(self, deployment_id: str) -> Optional[str]:
        """
        Get the status of a deployment.
        
        Args:
            deployment_id: ID of the deployment to check
            
        Returns:
            Deployment status string, or None if check fails
        """
        query = """
            query deployment($id: String!) {
                deployment(id: $id) {
                    id
                    status
                    staticUrl
                }
            }
        """
        
        try:
            result = self._execute_graphql(query, {"id": deployment_id})
            deployment = result.get("deployment", {})
            return deployment.get("status")
            
        except RuntimeError:
            return None
    
    def wait_for_deployment(
        self,
        deployment_id: str,
        timeout_seconds: int = RAILWAY_DEPLOYMENT_TIMEOUT_SECONDS
    ) -> bool:
        """
        Wait for a deployment to complete successfully.
        
        Args:
            deployment_id: ID of the deployment to wait for
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if deployment succeeded, False otherwise
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            status = self.get_deployment_status(deployment_id)
            
            if status == DeploymentStatus.SUCCESS.value:
                logger.info("Deployment %s succeeded", deployment_id)
                return True
            
            if status in (
                DeploymentStatus.FAILED.value,
                DeploymentStatus.CRASHED.value,
                DeploymentStatus.REMOVED.value
            ):
                logger.error("Deployment %s failed with status: %s", deployment_id, status)
                return False
            
            logger.debug("Deployment %s status: %s", deployment_id, status)
            time.sleep(RAILWAY_HEALTH_CHECK_INTERVAL_SECONDS)
        
        logger.error("Deployment %s timed out", deployment_id)
        return False
    
    def get_service_url(self, service_id: str) -> Optional[str]:
        """
        Get the public URL for a service.
        
        Args:
            service_id: ID of the service
            
        Returns:
            Service URL if available, None otherwise
        """
        query = """
            query service($id: String!) {
                service(id: $id) {
                    id
                    deployments(first: 1) {
                        edges {
                            node {
                                staticUrl
                            }
                        }
                    }
                }
            }
        """
        
        try:
            result = self._execute_graphql(query, {"id": service_id})
            service = result.get("service", {})
            deployments = service.get("deployments", {}).get("edges", [])
            
            if deployments:
                return deployments[0].get("node", {}).get("staticUrl")
            
            return None
            
        except RuntimeError:
            return None
    
    def verify_health(
        self,
        service_url: str,
        retries: int = RAILWAY_HEALTH_CHECK_RETRIES
    ) -> bool:
        """
        Verify a worker service is healthy via HTTP health check.
        
        Args:
            service_url: URL of the service to check
            retries: Number of retry attempts
            
        Returns:
            True if service responds to health check
        """
        health_url = f"https://{service_url}/health"
        
        for attempt in range(retries):
            try:
                response = self.http_client.get(health_url, timeout=10.0)
                if response.status_code == 200:
                    logger.info("Health check passed for %s", service_url)
                    return True
                    
            except httpx.HTTPError:
                pass
            
            logger.debug(
                "Health check attempt %d/%d for %s",
                attempt + 1, retries, service_url
            )
            time.sleep(RAILWAY_HEALTH_CHECK_INTERVAL_SECONDS)
        
        logger.warning("Health check failed for %s after %d attempts", service_url, retries)
        return False
    
    def delete_service(self, service_id: str) -> bool:
        """
        Delete a Railway service.
        
        Args:
            service_id: ID of the service to delete
            
        Returns:
            True if deleted successfully
        """
        mutation = """
            mutation serviceDelete($id: String!) {
                serviceDelete(id: $id)
            }
        """
        
        try:
            self._execute_graphql(mutation, {"id": service_id})
            logger.info("Deleted Railway service: %s", service_id)
            return True
        except RuntimeError as exc:
            logger.error("Failed to delete service %s: %s", service_id, exc)
            return False


class AutoScaler:
    """
    Manages automatic scaling of Juggernaut workers based on queue depth.
    
    The auto-scaler monitors task queue depth and active worker count,
    making scaling decisions based on configurable thresholds. Now includes
    Railway API integration for spawning real worker containers.
    """
    
    def __init__(
        self,
        db_endpoint: str,
        connection_string: str,
        config: Optional[ScalingConfig] = None,
        railway_config: Optional[RailwayConfig] = None
    ) -> None:
        """
        Initialize the auto-scaler.
        
        Args:
            db_endpoint: Neon database HTTP endpoint
            connection_string: PostgreSQL connection string
            config: Optional scaling configuration
            railway_config: Optional Railway API configuration
        """
        self.db_endpoint = db_endpoint
        self.connection_string = connection_string
        self.config = config or ScalingConfig()
        self.railway_config = railway_config or self._load_railway_config()
        self._last_scale_up: Optional[datetime] = None
        self._last_scale_down: Optional[datetime] = None
        self._http_client: Optional[httpx.Client] = None
        self._railway_client: Optional[RailwayClient] = None
    
    def _load_railway_config(self) -> RailwayConfig:
        """Load Railway configuration from environment variables."""
        return RailwayConfig(
            api_token=os.environ.get("RAILWAY_API_TOKEN", ""),
            project_id=os.environ.get(
                "RAILWAY_PROJECT_ID",
                "e785854e-d4d6-4975-a025-812b63fe8961"
            ),
            environment_id=os.environ.get(
                "RAILWAY_ENVIRONMENT_ID",
                "8bfa6a1a-92f4-4a42-bf51-194b1c844a76"
            ),
            template_service_id=os.environ.get(
                "RAILWAY_TEMPLATE_SERVICE_ID",
                "9b7370c6-7764-4eb6-a64c-75cce1d23e06"
            ),
            repo_url=os.environ.get(
                "RAILWAY_REPO_URL",
                ""
            ),
            branch=os.environ.get("RAILWAY_BRANCH", "main")
        )
    
    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0)
        return self._http_client
    
    @property
    def railway_client(self) -> RailwayClient:
        """Lazy-initialize Railway client."""
        if self._railway_client is None:
            self._railway_client = RailwayClient(self.railway_config)
        return self._railway_client
    
    def _execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query against the database.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Query result as dictionary
            
        Raises:
            RuntimeError: If query execution fails
        """
        try:
            response = self.http_client.post(
                self.db_endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Neon-Connection-String": self.connection_string
                },
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.error("Database query failed: %s", exc)
            raise RuntimeError(f"Database query failed: {exc}") from exc
    
    def get_queue_metrics(self) -> QueueMetrics:
        """
        Get current task queue metrics.
        
        Returns:
            QueueMetrics with current queue state
        """
        query = """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                COUNT(*) FILTER (WHERE status = 'waiting_approval') as waiting
            FROM governance_tasks
        """
        result = self._execute_query(query)
        rows = result.get("rows", [])
        
        if not rows:
            return QueueMetrics(0, 0, 0, 0)
        
        row = rows[0]
        pending = int(row.get("pending", 0) or 0)
        in_progress = int(row.get("in_progress", 0) or 0)
        waiting = int(row.get("waiting", 0) or 0)
        
        return QueueMetrics(
            pending_count=pending,
            in_progress_count=in_progress,
            waiting_approval_count=waiting,
            total_actionable=pending + in_progress
        )
    
    def get_worker_metrics(self) -> WorkerMetrics:
        """
        Get current worker metrics.
        
        Returns:
            WorkerMetrics with active worker state
        """
        stale_threshold = datetime.now(timezone.utc) - timedelta(
            seconds=HEARTBEAT_STALE_SECONDS
        )
        
        query = f"""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'active') as active,
                COUNT(*) FILTER (
                    WHERE status = 'active' 
                    AND last_heartbeat < '{stale_threshold.isoformat()}'
                ) as stale,
                COALESCE(SUM(max_concurrent_tasks), 0) as capacity
            FROM worker_registry
            WHERE status = 'active'
        """
        result = self._execute_query(query)
        rows = result.get("rows", [])
        
        if not rows:
            return WorkerMetrics(0, 0, 0, 0)
        
        row = rows[0]
        active = int(row.get("active", 0) or 0)
        stale = int(row.get("stale", 0) or 0)
        capacity = int(row.get("capacity", 0) or 0)
        
        in_progress_query = """
            SELECT COUNT(DISTINCT assigned_worker) as busy_workers
            FROM governance_tasks
            WHERE status = 'in_progress'
        """
        in_progress_result = self._execute_query(in_progress_query)
        in_progress_rows = in_progress_result.get("rows", [])
        busy = int(in_progress_rows[0].get("busy_workers", 0) or 0) if in_progress_rows else 0
        
        idle = max(0, active - stale - busy)
        
        return WorkerMetrics(
            active_count=active - stale,
            idle_count=idle,
            stale_count=stale,
            total_capacity=capacity
        )
    
    def _is_cooldown_active(self, action: ScalingAction) -> bool:
        """Check if cooldown period is active for an action."""
        now = datetime.now(timezone.utc)
        
        if action == ScalingAction.SCALE_UP:
            if self._last_scale_up is None:
                return False
            elapsed = (now - self._last_scale_up).total_seconds()
            return elapsed < self.config.scale_up_cooldown_seconds
        
        if action == ScalingAction.SCALE_DOWN:
            if self._last_scale_down is None:
                return False
            elapsed = (now - self._last_scale_down).total_seconds()
            return elapsed < self.config.scale_down_cooldown_seconds
        
        return False
    
    def evaluate_scaling(self) -> ScalingDecision:
        """
        Evaluate whether scaling is needed.
        
        Returns:
            ScalingDecision with recommended action
        """
        if not self.config.enabled:
            return ScalingDecision(
                action=ScalingAction.NO_ACTION,
                reason="Auto-scaling is disabled",
                current_workers=0,
                current_queue_depth=0
            )
        
        queue = self.get_queue_metrics()
        workers = self.get_worker_metrics()
        
        queue_depth = queue.pending_count
        active_workers = workers.active_count
        
        if queue_depth > self.config.scale_up_threshold:
            if active_workers >= self.config.max_workers:
                return ScalingDecision(
                    action=ScalingAction.NO_ACTION,
                    reason=f"At max workers ({self.config.max_workers})",
                    current_workers=active_workers,
                    current_queue_depth=queue_depth
                )
            
            if self._is_cooldown_active(ScalingAction.SCALE_UP):
                return ScalingDecision(
                    action=ScalingAction.NO_ACTION,
                    reason="Scale-up cooldown active",
                    current_workers=active_workers,
                    current_queue_depth=queue_depth
                )
            
            workers_needed = min(
                queue_depth // self.config.scale_up_threshold,
                self.config.max_workers - active_workers
            )
            
            return ScalingDecision(
                action=ScalingAction.SCALE_UP,
                reason=f"Queue depth {queue_depth} exceeds threshold {self.config.scale_up_threshold}",
                current_workers=active_workers,
                current_queue_depth=queue_depth,
                target_workers=active_workers + workers_needed,
                workers_to_add=workers_needed
            )
        
        if queue_depth <= self.config.scale_down_threshold and workers.idle_count > 0:
            if active_workers <= self.config.min_workers:
                return ScalingDecision(
                    action=ScalingAction.NO_ACTION,
                    reason=f"At min workers ({self.config.min_workers})",
                    current_workers=active_workers,
                    current_queue_depth=queue_depth
                )
            
            if self._is_cooldown_active(ScalingAction.SCALE_DOWN):
                return ScalingDecision(
                    action=ScalingAction.NO_ACTION,
                    reason="Scale-down cooldown active",
                    current_workers=active_workers,
                    current_queue_depth=queue_depth
                )
            
            workers_to_remove = min(
                workers.idle_count,
                active_workers - self.config.min_workers
            )
            
            return ScalingDecision(
                action=ScalingAction.SCALE_DOWN,
                reason=f"Queue empty with {workers.idle_count} idle workers",
                current_workers=active_workers,
                current_queue_depth=queue_depth,
                target_workers=active_workers - workers_to_remove,
                workers_to_remove=workers_to_remove
            )
        
        return ScalingDecision(
            action=ScalingAction.NO_ACTION,
            reason="Queue depth within normal range",
            current_workers=active_workers,
            current_queue_depth=queue_depth
        )
    
    def spawn_worker(
        self,
        worker_type: str = "agent-worker",
        use_railway: bool = True
    ) -> SpawnResult:
        """
        Spawn a new worker instance via Railway API.
        
        Creates a new Railway service, deploys it, verifies health,
        and registers in the database.
        
        Args:
            worker_type: Type of worker to spawn
            use_railway: If True, spawn via Railway API; if False, database-only
            
        Returns:
            SpawnResult with operation outcome
        """
        worker_id = f"{worker_type}-{uuid.uuid4().hex[:8]}"
        
        if not use_railway or not self.railway_config.api_token:
            # Fallback to database-only registration
            logger.warning(
                "Railway spawning disabled, creating database entry only for %s",
                worker_id
            )
            return self._spawn_database_only(worker_id)
        
        # Step 1: Create Railway service
        service_name = f"worker-{worker_id}"
        service_id = self.railway_client.create_service(service_name)
        
        if not service_id:
            return SpawnResult(
                success=False,
                worker_id=worker_id,
                error="Failed to create Railway service"
            )
        
        # Step 2: Connect service to repository
        if not self.railway_client.connect_service_to_repo(service_id):
            # Cleanup: delete the created service
            self.railway_client.delete_service(service_id)
            return SpawnResult(
                success=False,
                worker_id=worker_id,
                service_id=service_id,
                error="Failed to connect service to repository"
            )
        
        # Step 3: Trigger deployment
        deployment_id = self.railway_client.trigger_deployment(service_id)
        
        if not deployment_id:
            self.railway_client.delete_service(service_id)
            return SpawnResult(
                success=False,
                worker_id=worker_id,
                service_id=service_id,
                error="Failed to trigger deployment"
            )
        
        # Step 4: Wait for deployment to complete
        if not self.railway_client.wait_for_deployment(deployment_id):
            self.railway_client.delete_service(service_id)
            return SpawnResult(
                success=False,
                worker_id=worker_id,
                service_id=service_id,
                deployment_id=deployment_id,
                error="Deployment failed or timed out"
            )
        
        # Step 5: Verify health
        service_url = self.railway_client.get_service_url(service_id)
        health_verified = False
        
        if service_url:
            health_verified = self.railway_client.verify_health(service_url)
        
        if not health_verified:
            logger.warning(
                "Health check failed for %s, but deployment succeeded. "
                "Service may need manual verification.",
                worker_id
            )
        
        # Step 6: Register in database
        db_registered = self._register_worker_in_db(
            worker_id=worker_id,
            service_id=service_id,
            service_url=service_url
        )
        
        if not db_registered:
            logger.error(
                "Worker %s deployed but DB registration failed. "
                "Manual cleanup may be needed for service %s",
                worker_id, service_id
            )
            return SpawnResult(
                success=False,
                worker_id=worker_id,
                service_id=service_id,
                deployment_id=deployment_id,
                health_verified=health_verified,
                error="Database registration failed"
            )
        
        self._last_scale_up = datetime.now(timezone.utc)
        logger.info(
            "Successfully spawned worker %s (service: %s, health: %s)",
            worker_id, service_id, health_verified
        )
        
        return SpawnResult(
            success=True,
            worker_id=worker_id,
            service_id=service_id,
            deployment_id=deployment_id,
            health_verified=health_verified
        )
    
    def _spawn_database_only(self, worker_id: str) -> SpawnResult:
        """
        Fallback: Create database-only worker registration.
        
        Args:
            worker_id: Unique worker identifier
            
        Returns:
            SpawnResult indicating success/failure
        """
        registered = self._register_worker_in_db(worker_id)
        
        if registered:
            self._last_scale_up = datetime.now(timezone.utc)
            return SpawnResult(
                success=True,
                worker_id=worker_id,
                health_verified=False
            )
        
        return SpawnResult(
            success=False,
            worker_id=worker_id,
            error="Database registration failed"
        )
    
    def _register_worker_in_db(
        self,
        worker_id: str,
        service_id: Optional[str] = None,
        service_url: Optional[str] = None
    ) -> bool:
        """
        Register a worker in the database.
        
        Args:
            worker_id: Unique worker identifier
            service_id: Optional Railway service ID
            service_url: Optional service URL
            
        Returns:
            True if registration succeeded
        """
        # Escape single quotes for SQL
        safe_service_id = service_id.replace("'", "''") if service_id else ""
        safe_service_url = service_url.replace("'", "''") if service_url else ""
        
        metadata = {}
        if service_id:
            metadata["railway_service_id"] = service_id
        if service_url:
            metadata["service_url"] = service_url
        
        metadata_json = str(metadata).replace("'", '"') if metadata else "{}"
        
        query = f"""
            INSERT INTO worker_registry (
                worker_id, name, description, status, 
                max_concurrent_tasks, last_heartbeat, created_at,
                metadata
            ) VALUES (
                '{worker_id}',
                'Auto-scaled Worker',
                'Spawned by auto-scaler via Railway',
                'active',
                5,
                NOW(),
                NOW(),
                '{metadata_json}'::jsonb
            )
            ON CONFLICT (worker_id) DO UPDATE SET
                status = 'active',
                last_heartbeat = NOW()
            RETURNING worker_id
        """
        
        try:
            result = self._execute_query(query)
            rows = result.get("rows", [])
            if rows:
                logger.info("Registered worker in database: %s", worker_id)
                return True
            return False
        except RuntimeError as exc:
            logger.error("Failed to register worker %s: %s", worker_id, exc)
            return False
    
    def terminate_worker(self, worker_id: str) -> bool:
        """
        Terminate an idle worker and its Railway service.
        
        Args:
            worker_id: ID of worker to terminate
            
        Returns:
            True if terminated successfully
        """
        # First, get the Railway service ID from the database
        get_metadata_query = f"""
            SELECT metadata
            FROM worker_registry
            WHERE worker_id = '{worker_id}'
            AND status = 'active'
        """
        
        try:
            result = self._execute_query(get_metadata_query)
            rows = result.get("rows", [])
            
            service_id = None
            if rows and rows[0].get("metadata"):
                metadata = rows[0]["metadata"]
                if isinstance(metadata, dict):
                    service_id = metadata.get("railway_service_id")
            
            # Terminate Railway service if exists
            if service_id and self.railway_config.api_token:
                self.railway_client.delete_service(service_id)
            
            # Update database
            update_query = f"""
                UPDATE worker_registry
                SET status = 'offline', updated_at = NOW()
                WHERE worker_id = '{worker_id}'
                AND status = 'active'
                RETURNING worker_id
            """
            
            result = self._execute_query(update_query)
            if result.get("rowCount", 0) > 0:
                self._last_scale_down = datetime.now(timezone.utc)
                logger.info("Terminated worker: %s", worker_id)
                return True
                
        except RuntimeError as exc:
            logger.error("Failed to terminate worker %s: %s", worker_id, exc)
        
        return False
    
    def get_idle_workers(self) -> List[str]:
        """
        Get list of idle worker IDs.
        
        Returns:
            List of worker IDs that are idle
        """
        query = """
            SELECT wr.worker_id
            FROM worker_registry wr
            WHERE wr.status = 'active'
            AND NOT EXISTS (
                SELECT 1 FROM governance_tasks gt
                WHERE gt.assigned_worker = wr.worker_id
                AND gt.status = 'in_progress'
            )
            ORDER BY wr.last_heartbeat ASC
        """
        
        result = self._execute_query(query)
        rows = result.get("rows", [])
        return [row["worker_id"] for row in rows]
    
    def execute_scaling(self) -> Dict[str, Any]:
        """
        Evaluate and execute scaling decision.
        
        Returns:
            Dict with scaling action results
        """
        decision = self.evaluate_scaling()
        
        result: Dict[str, Any] = {
            "action": decision.action.value,
            "reason": decision.reason,
            "current_workers": decision.current_workers,
            "queue_depth": decision.current_queue_depth,
            "workers_added": [],
            "workers_removed": [],
            "errors": []
        }
        
        if decision.action == ScalingAction.SCALE_UP:
            for _ in range(decision.workers_to_add):
                spawn_result = self.spawn_worker()
                if spawn_result.success:
                    result["workers_added"].append({
                        "worker_id": spawn_result.worker_id,
                        "service_id": spawn_result.service_id,
                        "health_verified": spawn_result.health_verified
                    })
                else:
                    result["errors"].append({
                        "worker_id": spawn_result.worker_id,
                        "error": spawn_result.error
                    })
        
        elif decision.action == ScalingAction.SCALE_DOWN:
            idle_workers = self.get_idle_workers()
            for worker_id in idle_workers[:decision.workers_to_remove]:
                if self.terminate_worker(worker_id):
                    result["workers_removed"].append(worker_id)
        
        logger.info(
            "Scaling executed: action=%s, added=%d, removed=%d, errors=%d",
            decision.action.value,
            len(result["workers_added"]),
            len(result["workers_removed"]),
            len(result["errors"])
        )
        
        return result
    
    def log_scaling_event(self, decision: ScalingDecision) -> None:
        """
        Log scaling event to database for tracking.
        
        Args:
            decision: The scaling decision made
        """
        query = f"""
            INSERT INTO scaling_events (
                action, reason, workers_before, workers_after,
                queue_depth, created_at
            ) VALUES (
                '{decision.action.value}',
                '{decision.reason}',
                {decision.current_workers},
                {decision.target_workers or decision.current_workers},
                {decision.current_queue_depth},
                NOW()
            )
        """
        
        try:
            self._execute_query(query)
        except RuntimeError:
            logger.warning("Failed to log scaling event (table may not exist)")


def create_auto_scaler(
    db_endpoint: str,
    connection_string: str,
    config: Optional[ScalingConfig] = None,
    railway_config: Optional[RailwayConfig] = None
) -> AutoScaler:
    """
    Factory function to create an AutoScaler.
    
    Args:
        db_endpoint: Neon database HTTP endpoint
        connection_string: PostgreSQL connection string
        config: Optional scaling configuration
        railway_config: Optional Railway API configuration
        
    Returns:
        Configured AutoScaler instance
    """
    return AutoScaler(db_endpoint, connection_string, config, railway_config)

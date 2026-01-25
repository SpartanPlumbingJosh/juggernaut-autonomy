import logging
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Constants
HEALTH_ENDPOINT: str = "/health"
SERVICE_NAME: str = "juggernaut-mcp"
DEFAULT_VERSION: str = "unknown"
ENV_VERSION_KEY: str = "JUGGERNAUT_MCP_VERSION"
ENVIRONMENT_KEY: str = "ENVIRONMENT"
DEFAULT_ENVIRONMENT: str = "unknown"
DEFAULT_HOST: str = "0.0.0.0"
DEFAULT_PORT: int = 8000
TIMESTAMP_PRECISION: int = 3

# Service start time used to compute uptime
START_TIME: float = time.time()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


class HealthStatus(BaseModel):
    """Represents the health status response for the service.

    Attributes:
        service: Name of the service.
        status: Health status string (e.g., 'healthy', 'unhealthy').
        uptime_seconds: Service uptime in seconds.
        environment: Name of the deployment environment.
        version: Service version string.
        timestamp: Unix timestamp of the health check response.
        details: Optional dictionary containing additional diagnostic data.
    """

    service: str
    status: str
    uptime_seconds: float
    environment: str
    version: str
    timestamp: float
    details: Optional[Dict[str, Any]] = None


def _get_service_version() -> str:
    """Retrieve the service version from the environment.

    Returns:
        The service version string, or a default value if not set.
    """
    version: str = os.getenv(ENV_VERSION_KEY, DEFAULT_VERSION)
    return version


def _get_environment() -> str:
    """Retrieve the deployment environment from the environment variables.

    Returns:
        The environment name, or a default value if not set.
    """
    environment: str = os.getenv(ENVIRONMENT_KEY, DEFAULT_ENVIRONMENT)
    return environment


def _get_uptime_seconds(start_time: float) -> float:
    """Compute the service uptime in seconds.

    Args:
        start_time: The Unix timestamp when the service started.

    Returns:
        The uptime in seconds.
    """
    uptime: float = time.time() - start_time
    return round(uptime, TIMESTAMP_PRECISION)


def _build_healthy_response() -> HealthStatus:
    """Build a healthy health-check response object.

    Returns:
        A populated HealthStatus instance representing a healthy service.
    """
    health_status = HealthStatus(
        service=SERVICE_NAME,
        status="healthy",
        uptime_seconds=_get_uptime_seconds(START_TIME),
        environment=_get_environment(),
        version=_get_service_version(),
        timestamp=round(time.time(), TIMESTAMP_PRECISION),
        details=None,
    )
    return health_status


def _build_unhealthy_response(error_message: str) -> JSONResponse:
    """Build an unhealthy health-check JSON response.

    Args:
        error_message: A message describing the failure reason.

    Returns:
        A JSONResponse object containing the unhealthy status.
    """
    logger.error("Health check failed: %s", error_message)
    body: Dict[str, Any] = {
        "service": SERVICE_NAME,
        "status": "unhealthy",
        "uptime_seconds": _get_uptime_seconds(START_TIME),
        "environment": _get_environment(),
        "version": _get_service_version(),
        "timestamp": round(time.time(), TIMESTAMP_PRECISION),
        "details": {"error": error_message},
    }
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)


router: APIRouter = APIRouter()


@router.get(
    HEALTH_ENDPOINT,
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Service health check",
    tags=["health"],
)
async def health_check() -> JSONResponse:
    """Health-check endpoint for the juggernaut-mcp service.

    Returns:
        A JSONResponse containing the health status of the service.
    """
    try:
        # Placeholder for dependency checks (databases, message brokers, etc.)
        # Example: await some_dependency.ping()

        health_status: HealthStatus = _build_healthy_response()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=health_status.dict(),
        )
    except Exception as exc:
        logger.exception("Unhandled exception during health check")
        return _build_unhealthy_response(error_message=str(exc))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A configured FastAPI application instance.
    """
    application = FastAPI(title=SERVICE_NAME)
    application.include_router(router)
    return application


app: FastAPI = create_app()


if __name__ == "__main__":
    try:
        import uvicorn  # type: ignore[import-untyped]

        uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)
    except ImportError as import_error:
        logger.error(
            "uvicorn is required to run the application directly: %s",
            import_error,
        )
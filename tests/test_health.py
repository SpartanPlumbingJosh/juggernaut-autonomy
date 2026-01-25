import json
import os
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import health


@pytest.fixture
def fixed_time() -> float:
    # Arbitrary fixed Unix timestamp
    return 1_700_000_000.1234


@pytest.fixture
def mock_time(monkeypatch, fixed_time: float):
    """Patch time.time in the health module to return a fixed value."""
    monkeypatch.setattr(health.time, "time", lambda: fixed_time)
    return fixed_time


@pytest.fixture
def clear_env(monkeypatch):
    """Clear relevant environment variables for each test."""
    monkeypatch.delenv(health.ENV_VERSION_KEY, raising=False)
    monkeypatch.delenv(health.ENVIRONMENT_KEY, raising=False)


@pytest.fixture
def test_client() -> TestClient:
    """Create a new FastAPI test client for each test."""
    app: FastAPI = health.create_app()
    return TestClient(app)


def test_health_status_model_basic():
    """HealthStatus model should accept and expose provided fields."""
    details: Dict[str, Any] = {"info": "test"}
    hs = health.HealthStatus(
        service="svc",
        status="healthy",
        uptime_seconds=1.23,
        environment="dev",
        version="1.0.0",
        timestamp=123.456,
        details=details,
    )

    assert hs.service == "svc"
    assert hs.status == "healthy"
    assert hs.uptime_seconds == 1.23
    assert hs.environment == "dev"
    assert hs.version == "1.0.0"
    assert hs.timestamp == 123.456
    assert hs.details == details


def test_health_status_model_details_optional():
    """HealthStatus.details should be optional and default to None."""
    hs = health.HealthStatus(
        service="svc",
        status="healthy",
        uptime_seconds=0.0,
        environment="env",
        version="v",
        timestamp=0.0,
    )
    assert hs.details is None


def test_get_service_version_default_when_env_missing(monkeypatch, clear_env):
    """_get_service_version should return default when env var is not set."""
    version = health._get_service_version()
    assert version == health.DEFAULT_VERSION


def test_get_service_version_uses_env(monkeypatch, clear_env):
    """_get_service_version should respect environment variable."""
    monkeypatch.setenv(health.ENV_VERSION_KEY, "2.3.4")
    version = health._get_service_version()
    assert version == "2.3.4"


def test_get_service_version_allows_empty_string(monkeypatch, clear_env):
    """_get_service_version should allow empty string if explicitly set."""
    monkeypatch.setenv(health.ENV_VERSION_KEY, "")
    version = health._get_service_version()
    # os.getenv returns empty string; no fallback should be used
    assert version == ""


def test_get_environment_default_when_env_missing(monkeypatch, clear_env):
    """_get_environment should return default when env var is not set."""
    environment = health._get_environment()
    assert environment == health.DEFAULT_ENVIRONMENT


def test_get_environment_uses_env(monkeypatch, clear_env):
    """_get_environment should respect environment variable."""
    monkeypatch.setenv(health.ENVIRONMENT_KEY, "production")
    environment = health._get_environment()
    assert environment == "production"


def test_get_environment_allows_empty_string(monkeypatch, clear_env):
    """_get_environment should allow empty string if explicitly set."""
    monkeypatch.setenv(health.ENVIRONMENT_KEY, "")
    environment = health._get_environment()
    assert environment == ""


def test_get_uptime_seconds_rounding(monkeypatch):
    """_get_uptime_seconds should compute and round uptime correctly."""
    start_time = 1_000.0
    current_time = 1_001.23456
    monkeypatch.setattr(health.time, "time", lambda: current_time)

    uptime = health._get_uptime_seconds(start_time)
    # Rounded to TIMESTAMP_PRECISION (3)
    assert uptime == round(current_time - start_time, health.TIMESTAMP_PRECISION)


def test_build_healthy_response_structure(monkeypatch, clear_env, mock_time):
    """_build_healthy_response should return a properly populated HealthStatus."""
    # Fix START_TIME-relative uptime as well
    # Simulate START_TIME being just 10 seconds before fixed time
    start_time = mock_time - 10.12345
    monkeypatch.setattr(health, "START_TIME", start_time)

    monkeypatch.setenv(health.ENVIRONMENT_KEY, "test-env")
    monkeypatch.setenv(health.ENV_VERSION_KEY, "9.9.9")

    health_status = health._build_healthy_response()

    assert isinstance(health_status, health.HealthStatus)
    assert health_status.service == health.SERVICE_NAME
    assert health_status.status == "healthy"
    assert health_status.environment == "test-env"
    assert health_status.version == "9.9.9"
    assert health_status.details is None
    # Uptime is time - START_TIME, rounded
    expected_uptime = round(mock_time - start_time, health.TIMESTAMP_PRECISION)
    assert health_status.uptime_seconds == expected_uptime
    # Timestamp should be rounded to TIMESTAMP_PRECISION
    assert health_status.timestamp == round(mock_time, health.TIMESTAMP_PRECISION)


def test_build_unhealthy_response_structure(
    monkeypatch, clear_env, mock_time, caplog
):
    """_build_unhealthy_response should return JSONResponse with proper body and log."""
    start_time = mock_time - 5.4321
    monkeypatch.setattr(health, "START_TIME", start_time)
    monkeypatch.setenv(health.ENVIRONMENT_KEY, "staging")
    monkeypatch.setenv(health.ENV_VERSION_KEY, "1.2.3")

    error_message = "dependency failure"

    with caplog.at_level("ERROR", logger=health.logger.name):
        response = health._build_unhealthy_response(error_message)

    assert response.status_code == 503

    body = json.loads(response.body.decode("utf-8"))
    assert body["service"] == health.SERVICE_NAME
    assert body["status"] == "unhealthy"
    assert body["environment"] == "staging"
    assert body["version"] == "1.2.3"
    assert body["details"]["error"] == error_message
    expected_uptime = round(mock_time - start_time, health.TIMESTAMP_PRECISION)
    assert body["uptime_seconds"] == expected_uptime
    assert body["timestamp"] == round(mock_time, health.TIMESTAMP_PRECISION)

    # Ensure an error log was emitted with the message
    assert any(
        error_message in record.getMessage() and record.levelname == "ERROR"
        for record in caplog.records
    )


def test_router_is_apirouter_instance():
    """router should be an APIRouter instance and expose the health endpoint."""
    paths = [route.path for route in health.router.routes]
    assert health.HEALTH_ENDPOINT in paths


def test_create_app_returns_fastapi_app():
    """create_app should return a FastAPI app with expected title and routes."""
    app = health.create_app()
    assert isinstance(app, FastAPI)
    assert app.title == health.SERVICE_NAME

    # Check that /health route is registered
    paths = [route.path for route in app.routes]
    assert health.HEALTH_ENDPOINT in paths


def test_global_app_instance_is_fastapi_app():
    """Global app should be a FastAPI instance with the health router included."""
    assert isinstance(health.app, FastAPI)
    paths = [route.path for route in health.app.routes]
    assert health.HEALTH_ENDPOINT in paths


def test_health_check_success_via_test_client(test_client, clear_env, monkeypatch):
    """health_check endpoint should return 200 and healthy status on success."""
    # Control environment
    monkeypatch.setenv(health.ENVIRONMENT_KEY, "dev")
    monkeypatch.setenv(health.ENV_VERSION_KEY, "0.1.0")

    response = test_client.get(health.HEALTH_ENDPOINT)
    assert response.status_code == 200

    body = response.json()
    assert body["service"] == health.SERVICE_NAME
    assert body["status"] == "healthy"
    assert body["environment"] == "dev"
    assert body["version"] == "0.1.0"
    assert isinstance(body["uptime_seconds"], float)
    assert "timestamp" in body
    # details should be omitted or null; both acceptable; ensure key exists
    assert "details" in body


def test_health_check_uses_helpers(monkeypatch, test_client):
    """health_check should use helper functions to populate fields."""
    # Track calls to helper functions to ensure they are used
    called = {"healthy": False}

    def fake_build_healthy():
        called["healthy"] = True
        return health.HealthStatus(
            service="svc",
            status="healthy",
            uptime_seconds=1.0,
            environment="env",
            version="v",
            timestamp=0.0,
        )

    monkeypatch.setattr(health, "_build_healthy_response", fake_build_healthy)

    response = test_client.get(health.HEALTH_ENDPOINT)
    assert response.status_code == 200
    assert called["healthy"] is True
    assert response.json()["service"] == "svc"


def test_health_check_unhealthy_on_exception(monkeypatch, test_client):
    """health_check should return 503 unhealthy response when an exception occurs."""
    def raise_error():
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(health, "_build_healthy_response", raise_error)

    response = test_client.get(health.HEALTH_ENDPOINT)
    assert response.status_code == 503

    body = response.json()
    assert body["status"] == "unhealthy"
    assert "simulated failure" in body["details"]["error"]


@pytest.mark.asyncio
async def test_health_check_direct_call_success(monkeypatch, clear_env):
    """Directly calling health_check coroutine should return a JSONResponse."""
    # Provide deterministic healthy response
    hs = health.HealthStatus(
        service="svc",
        status="healthy",
        uptime_seconds=1.0,
        environment="env",
        version="v",
        timestamp=0.0,
    )

    monkeypatch.setattr(health, "_build_healthy_response", lambda: hs)

    response = await health.health_check()
    assert response.status_code == 200

    body = json.loads(response.body.decode("utf-8"))
    assert body == hs.dict()


@pytest.mark.asyncio
async def test_health_check_direct_call_exception(monkeypatch):
    """Directly calling health_check should handle exceptions from helper."""
    def raise_error():
        raise ValueError("boom")

    monkeypatch.setattr(health, "_build_healthy_response", raise_error)

    response = await health.health_check()
    assert response.status_code == 503

    body = json.loads(response.body.decode("utf-8"))
    assert body["status"] == "unhealthy"
    assert "boom" in body["details"]["error"]
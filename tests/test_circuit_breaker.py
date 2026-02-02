"""
Unit tests for the circuit breaker pattern implementation.

Tests the circuit breaker states, transitions, and behavior under various conditions.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from core.circuit_breaker import CircuitBreaker, CircuitBreakerState


@pytest.fixture
def circuit_breaker():
    """Create a test circuit breaker with default settings."""
    return CircuitBreaker(
        name="test_breaker",
        failure_threshold=3,
        reset_timeout=1.0,
        half_open_timeout=0.5
    )


class TestCircuitBreaker:
    """Test suite for the CircuitBreaker class."""

    def test_initial_state(self, circuit_breaker):
        """Test that circuit breaker starts in CLOSED state."""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.is_closed
        assert not circuit_breaker.is_open
        assert not circuit_breaker.is_half_open

    async def test_successful_execution(self, circuit_breaker):
        """Test that successful execution doesn't change state."""
        mock_func = AsyncMock(return_value="success")
        
        result = await circuit_breaker.call(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    async def test_failure_below_threshold(self, circuit_breaker):
        """Test that failures below threshold don't open the circuit."""
        mock_func = AsyncMock(side_effect=ValueError("test error"))
        
        # First failure
        with pytest.raises(ValueError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 1
        
        # Second failure
        with pytest.raises(ValueError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 2

    async def test_failure_threshold_opens_circuit(self, circuit_breaker):
        """Test that reaching failure threshold opens the circuit."""
        mock_func = AsyncMock(side_effect=ValueError("test error"))
        
        # Three failures (threshold)
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 3
        
        # Next call should fail fast without calling function
        with pytest.raises(CircuitBreaker.CircuitOpenError):
            await circuit_breaker.call(mock_func)
        
        # Function should not have been called again
        assert mock_func.call_count == 3

    async def test_reset_timeout_transitions_to_half_open(self, circuit_breaker):
        """Test that circuit transitions to half-open after reset timeout."""
        mock_func = AsyncMock(side_effect=ValueError("test error"))
        
        # Open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for reset timeout
        await asyncio.sleep(1.1)
        
        # Circuit should now be half-open
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN

    async def test_successful_call_in_half_open_closes_circuit(self, circuit_breaker):
        """Test that successful call in half-open state closes the circuit."""
        mock_func = AsyncMock(side_effect=[
            ValueError("test error"),  # First 3 calls fail
            ValueError("test error"),
            ValueError("test error"),
            "success"  # Then succeeds after reset
        ])
        
        # Open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for reset timeout
        await asyncio.sleep(1.1)
        
        # Circuit should now be half-open
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
        
        # Successful call should close the circuit
        result = await circuit_breaker.call(mock_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0

    async def test_failure_in_half_open_reopens_circuit(self, circuit_breaker):
        """Test that failure in half-open state reopens the circuit."""
        mock_func = AsyncMock(side_effect=ValueError("test error"))
        
        # Open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for reset timeout
        await asyncio.sleep(1.1)
        
        # Circuit should now be half-open
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
        
        # Failure in half-open should reopen the circuit
        with pytest.raises(ValueError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 1  # Reset to 1 after half-open failure

    async def test_circuit_breaker_as_async_context_manager(self, circuit_breaker):
        """Test circuit breaker as an async context manager."""
        mock_func = AsyncMock(return_value="success")
        
        async with circuit_breaker:
            result = await mock_func("arg1")
        
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        mock_func.assert_called_once_with("arg1")

    async def test_circuit_breaker_as_async_context_manager_with_failure(self, circuit_breaker):
        """Test circuit breaker as an async context manager with failure."""
        mock_func = AsyncMock(side_effect=ValueError("test error"))
        
        # First two failures
        for _ in range(2):
            with pytest.raises(ValueError):
                async with circuit_breaker:
                    await mock_func()
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 2
        
        # Third failure opens the circuit
        with pytest.raises(ValueError):
            async with circuit_breaker:
                await mock_func()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 3
        
        # Next attempt should fail fast
        with pytest.raises(CircuitBreaker.CircuitOpenError):
            async with circuit_breaker:
                await mock_func()
        
        # Function should not have been called again
        assert mock_func.call_count == 3

    async def test_excluded_exceptions(self):
        """Test that excluded exceptions don't count towards failure threshold."""
        circuit_breaker = CircuitBreaker(
            name="test_breaker",
            failure_threshold=2,
            excluded_exceptions=[KeyError]
        )
        
        mock_func = AsyncMock(side_effect=[
            KeyError("excluded"),  # This shouldn't count
            ValueError("counts"),  # This counts
            KeyError("excluded again"),  # This shouldn't count
            ValueError("counts again")  # This opens the circuit
        ])
        
        # KeyError should not count towards failures
        with pytest.raises(KeyError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        
        # ValueError should count
        with pytest.raises(ValueError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 1
        
        # KeyError should not count
        with pytest.raises(KeyError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 1
        
        # Second ValueError should open circuit
        with pytest.raises(ValueError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 2

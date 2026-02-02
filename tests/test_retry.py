"""
Unit tests for the retry module with exponential backoff.

Tests the retry functionality with various configurations and scenarios.
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, Mock, patch

from core.retry import retry, async_retry


class TestRetry:
    """Test suite for the retry decorator."""

    def test_successful_execution_no_retry(self):
        """Test that successful execution doesn't trigger retries."""
        mock_func = Mock(return_value="success")
        
        @retry(max_retries=3, base_delay=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        mock_func.assert_called_once()

    def test_retry_until_success(self):
        """Test that function is retried until success."""
        mock_func = Mock(side_effect=[ValueError("error"), ValueError("error"), "success"])
        
        @retry(max_retries=3, base_delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 3

    def test_max_retries_exceeded(self):
        """Test that exception is raised when max retries are exceeded."""
        mock_func = Mock(side_effect=ValueError("persistent error"))
        
        @retry(max_retries=3, base_delay=0.01)
        def test_func():
            return mock_func()
        
        with pytest.raises(ValueError, match="persistent error"):
            test_func()
        
        assert mock_func.call_count == 4  # Initial call + 3 retries

    def test_specific_exceptions(self):
        """Test that only specified exceptions trigger retries."""
        mock_func = Mock(side_effect=[ValueError("retry"), KeyError("no retry")])
        
        @retry(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        def test_func():
            return mock_func()
        
        # Should retry on ValueError, then fail with KeyError
        with pytest.raises(KeyError, match="no retry"):
            test_func()
        
        assert mock_func.call_count == 2  # Initial ValueError + KeyError

    def test_backoff_timing(self):
        """Test that backoff timing follows exponential pattern."""
        mock_func = Mock(side_effect=[ValueError("error"), ValueError("error"), ValueError("error"), "success"])
        
        @retry(max_retries=3, base_delay=0.05, max_delay=1.0)
        def test_func():
            return mock_func()
        
        start_time = time.time()
        result = test_func()
        elapsed_time = time.time() - start_time
        
        assert result == "success"
        assert mock_func.call_count == 4
        
        # Check that elapsed time is at least the sum of delays
        # base_delay * (1 + 2 + 4) = 0.05 * 7 = 0.35
        assert elapsed_time >= 0.35

    def test_jitter(self):
        """Test that jitter is applied to backoff delays."""
        mock_sleep = Mock()
        
        with patch('time.sleep', mock_sleep):
            mock_func = Mock(side_effect=[ValueError("error"), ValueError("error"), "success"])
            
            @retry(max_retries=2, base_delay=1.0, jitter=0.5)
            def test_func():
                return mock_func()
            
            test_func()
            
            # Check that sleep was called with jittered values
            assert mock_sleep.call_count == 2
            
            # First delay should be between 0.5 and 1.5 (1.0 ± 0.5)
            assert 0.5 <= mock_sleep.call_args_list[0][0][0] <= 1.5
            
            # Second delay should be between 1.0 and 3.0 (2.0 ± 1.0)
            assert 1.0 <= mock_sleep.call_args_list[1][0][0] <= 3.0

    def test_on_retry_callback(self):
        """Test that on_retry callback is called with correct arguments."""
        on_retry_mock = Mock()
        mock_func = Mock(side_effect=[ValueError("error"), "success"])
        
        @retry(max_retries=3, base_delay=0.01, on_retry=on_retry_mock)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 2
        
        # Check that on_retry was called once with the correct arguments
        on_retry_mock.assert_called_once()
        args = on_retry_mock.call_args[0]
        assert args[0] == 1  # retry_number
        assert isinstance(args[1], ValueError)  # exception
        assert isinstance(args[2], float)  # delay


class TestAsyncRetry:
    """Test suite for the async_retry decorator."""

    async def test_successful_execution_no_retry(self):
        """Test that successful execution doesn't trigger retries."""
        mock_func = AsyncMock(return_value="success")
        
        @async_retry(max_retries=3, base_delay=0.1)
        async def test_func():
            return await mock_func()
        
        result = await test_func()
        
        assert result == "success"
        mock_func.assert_called_once()

    async def test_retry_until_success(self):
        """Test that function is retried until success."""
        mock_func = AsyncMock(side_effect=[ValueError("error"), ValueError("error"), "success"])
        
        @async_retry(max_retries=3, base_delay=0.01)
        async def test_func():
            return await mock_func()
        
        result = await test_func()
        
        assert result == "success"
        assert mock_func.call_count == 3

    async def test_max_retries_exceeded(self):
        """Test that exception is raised when max retries are exceeded."""
        mock_func = AsyncMock(side_effect=ValueError("persistent error"))
        
        @async_retry(max_retries=3, base_delay=0.01)
        async def test_func():
            return await mock_func()
        
        with pytest.raises(ValueError, match="persistent error"):
            await test_func()
        
        assert mock_func.call_count == 4  # Initial call + 3 retries

    async def test_specific_exceptions(self):
        """Test that only specified exceptions trigger retries."""
        mock_func = AsyncMock(side_effect=[ValueError("retry"), KeyError("no retry")])
        
        @async_retry(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        async def test_func():
            return await mock_func()
        
        # Should retry on ValueError, then fail with KeyError
        with pytest.raises(KeyError, match="no retry"):
            await test_func()
        
        assert mock_func.call_count == 2  # Initial ValueError + KeyError

    async def test_backoff_timing(self):
        """Test that backoff timing follows exponential pattern."""
        mock_sleep = AsyncMock()
        
        with patch('asyncio.sleep', mock_sleep):
            mock_func = AsyncMock(side_effect=[ValueError("error"), ValueError("error"), "success"])
            
            @async_retry(max_retries=2, base_delay=1.0)
            async def test_func():
                return await mock_func()
            
            await test_func()
            
            # Check that sleep was called with exponential backoff
            assert mock_sleep.call_count == 2
            assert mock_sleep.call_args_list[0][0][0] >= 1.0  # First delay
            assert mock_sleep.call_args_list[1][0][0] >= 2.0  # Second delay

    async def test_on_retry_callback(self):
        """Test that on_retry callback is called with correct arguments."""
        on_retry_mock = Mock()
        mock_func = AsyncMock(side_effect=[ValueError("error"), "success"])
        
        @async_retry(max_retries=3, base_delay=0.01, on_retry=on_retry_mock)
        async def test_func():
            return await mock_func()
        
        result = await test_func()
        
        assert result == "success"
        assert mock_func.call_count == 2
        
        # Check that on_retry was called once with the correct arguments
        on_retry_mock.assert_called_once()
        args = on_retry_mock.call_args[0]
        assert args[0] == 1  # retry_number
        assert isinstance(args[1], ValueError)  # exception
        assert isinstance(args[2], float)  # delay

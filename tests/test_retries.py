"""Tests for retry and timeout adaptation strategies."""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from task.retries import RetryConfig, retry_with_backoff


class TestRetryWithBackoff:
    """Tests for @retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        """Verify decorator returns immediately on success."""
        call_count = 0

        @retry_with_backoff()
        async def succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await succeeds()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self):
        """Verify decorator retries once and succeeds."""
        call_count = 0

        @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.01))
        async def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("first attempt fails")
            return "success"

        result = await fails_once()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_playwright_timeout_error(self):
        """Verify decorator retries real Playwright timeouts from the scraper."""
        call_count = 0

        @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.01, jitter=False))
        async def fails_once_with_playwright_timeout():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise PlaywrightTimeoutError("playwright timeout")
            return "success"

        result = await fails_once_with_playwright_timeout()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_fails_after_max_attempts(self):
        """Verify decorator gives up after max_attempts."""
        call_count = 0

        @retry_with_backoff(RetryConfig(max_attempts=2, base_delay=0.01))
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("always fails")

        with pytest.raises(TimeoutError, match="always fails"):
            await always_fails()

        assert call_count == 2  # Initial + 1 retry

    @pytest.mark.asyncio
    async def test_respects_custom_exception_types(self):
        """Verify decorator only retries specified exceptions."""

        @retry_with_backoff(
            RetryConfig(max_attempts=3, base_delay=0.01),
            exceptions=(ValueError,),
        )
        async def raises_timeout():
            raise TimeoutError("not configured to retry this")

        with pytest.raises(TimeoutError, match="not configured"):
            await raises_timeout()

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Verify delays follow exponential backoff (0.5s, 1s, 2s for base=2)."""
        timings = []

        @retry_with_backoff(
            RetryConfig(
                max_attempts=3,
                base_delay=0.01,
                exponential_base=2.0,
                jitter=False,
            )
        )
        async def fails_twice():
            timings.append(time.time())
            if len(timings) < 3:
                raise TimeoutError("retry")
            return "success"

        await fails_twice()
        assert len(timings) == 3

        # Check exponential progression (0.01, 0.02, 0.04 with some tolerance)
        delay_1 = timings[1] - timings[0]
        delay_2 = timings[2] - timings[1]
        assert 0.009 < delay_1 < 0.02  # 0.01s ±
        assert 0.019 < delay_2 < 0.04  # 0.02s ±

    @pytest.mark.asyncio
    async def test_respects_max_delay_cap(self):
        """Verify backoff doesn't exceed max_delay."""

        @retry_with_backoff(
            RetryConfig(
                max_attempts=4,
                base_delay=10.0,
                max_delay=0.05,
                exponential_base=2.0,
                jitter=False,
            )
        )
        async def fails_thrice():
            raise TimeoutError("retry")

        start = time.time()
        with pytest.raises(TimeoutError):
            await fails_thrice()
        elapsed = time.time() - start

        # Max delays: 0.05s + 0.05s = 0.1s (not 10 + 20 + 40 = 70s)
        assert elapsed < 0.2, f"Took too long: {elapsed}s (expected <0.2s)"



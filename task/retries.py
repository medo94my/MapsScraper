"""Retry strategies for resilient web scraping."""

import asyncio
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar

try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
except Exception:  # pragma: no cover - fallback for environments without Playwright
    PlaywrightTimeoutError = TimeoutError

from task.logger import get_logger

logger = get_logger("task.retries")

T = TypeVar("T")

SCRAPER_TIMEOUT_EXCEPTIONS = (TimeoutError, PlaywrightTimeoutError)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    """Maximum number of retry attempts (including initial attempt)."""

    base_delay: float = 0.5
    """Initial delay in seconds before first retry."""

    max_delay: float = 10.0
    """Maximum delay cap in seconds."""

    exponential_base: float = 2.0
    """Multiplier for exponential backoff (delay *= exponential_base)."""

    jitter: bool = True
    """If True, add ±20% random jitter to delay to avoid thundering herd."""


def retry_with_backoff(
    config: RetryConfig | None = None,
    exceptions: tuple[type[Exception], ...] = SCRAPER_TIMEOUT_EXCEPTIONS,
):
    """Decorator for async functions with exponential backoff retry.

    Retries the decorated async function on specified exceptions with
    exponential backoff. Logs each retry attempt and final failure.

    Args:
        config: RetryConfig instance. Defaults to RetryConfig() (3 attempts,
            0.5s base delay, exponential backoff).
        exceptions: Tuple of exception types to catch and retry on.
            Defaults to built-in TimeoutError plus Playwright TimeoutError.

    Returns:
        Decorated async function that retries on exception.

    Example:
        >>> @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.5))
        ... async def fetch_data(url):
        ...     return await browser.goto(url)
        >>> await fetch_data("https://example.com")
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            func_name = func.__name__

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == config.max_attempts:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func_name,
                            config.max_attempts,
                            e,
                        )
                        raise

                    delay = min(
                        config.base_delay
                        * (config.exponential_base ** (attempt - 1)),
                        config.max_delay,
                    )
                    if config.jitter:
                        # Add ±20% jitter to avoid thundering herd
                        jitter_factor = 1.0 + (hash(id(func)) % 40 - 20) / 100
                        delay *= jitter_factor

                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying in %.2fs...",
                        func_name,
                        attempt,
                        config.max_attempts,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)

            # Should never reach here (raise above), but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator

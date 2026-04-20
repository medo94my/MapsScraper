# Retry module reference

This page documents retry utilities that improve resilience against transient
network and page-load failures.

## Module purpose

task/retries.py provides retry configuration and an async decorator for
exponential backoff.

## Retry timeout exceptions

SCRAPER_TIMEOUT_EXCEPTIONS contains the default retry exception classes.

Behavior:
- includes built-in TimeoutError.
- includes Playwright timeout error when Playwright is importable.

## Dataclass: RetryConfig

RetryConfig defines retry policy values.

Fields:
- max_attempts: int = 3
- base_delay: float = 0.5
- max_delay: float = 10.0
- exponential_base: float = 2.0
- jitter: bool = True

Operational notes:
- larger max_attempts improve recovery but increase per-item latency.
- jitter helps avoid synchronized retry spikes.

## Function: retry_with_backoff(config=None, exceptions=...)

This function returns a decorator for async call retry.

Behavior:
- wraps async function and retries matching exceptions.
- uses exponential backoff with max delay cap.
- logs retry attempts and final failure.
- re-raises the final exception after max attempts.

Usage notes:
- use on idempotent extraction-level operations.
- avoid use around broad multi-step workflows with hard-to-reverse side effects.

## Current integration

MapsScraper uses this decorator on _extract_listing_from_href to recover from
transient detail-page timeout failures.

## Next steps

If you tune retry policy values, test both success-recovery and max-attempt
failure paths.

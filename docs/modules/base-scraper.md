# BaseScraper reference

This page documents the abstract base class that provides shared runtime,
concurrency, checkpoint orchestration, and I/O helpers for scraper
implementations.

## Module purpose

task/base.py contains the stable skeleton that concrete scrapers build on.
Subclasses must only implement scrape, while BaseScraper handles common
infrastructure.

## Class: BaseScraper

BaseScraper is an abstract base class for Playwright-based scrapers.

### __init__(headless: bool = True, max_concurrency: int | None = None)

This constructor initializes runtime settings.

Behavior:
- stores headless mode.
- resolves max_concurrency from SCRAPER_MAX_CONCURRENCY when omitted.
- enforces a minimum value of 1.

### _env_int(name: str, default: int) -> int

This helper parses an integer environment variable safely.

Behavior:
- returns default when variable is unset.
- returns default and logs warning when value is invalid.

### scrape(prompts: list[Prompt], limit: int) -> list[Listing]

This abstract async function is the required subclass contract.

Implementation requirement:
- concrete scrapers must implement this method.

### run(prompts, limit=10, checkpoint=None, show_progress=True)

This function is the synchronous entry point used by scripts and drivers.

Behavior:
- returns empty list for empty input.
- without checkpoint, runs scrape in a dedicated event loop.
- with checkpoint, routes to checkpoint-enabled orchestration.
- logs and returns empty list on top-level failure.

### _run_with_checkpoint(...)

This internal function wraps checkpoint mode in a sync call.

Behavior:
- creates and closes an event loop around _run_with_checkpoint_async.

### _run_with_checkpoint_async(...)

This function runs prompts concurrently with checkpoint and progress semantics.

Behavior:
- filters already completed prompts first.
- uses semaphore to enforce max_concurrency.
- for each prompt, marks started, scrapes, saves listings, and marks success.
- marks failed on exception and continues remaining work.
- uses locks for checkpoint writes, progress output, and shared listings list.

Reliability note:
- listing persistence happens per prompt, reducing crash-loss window.

### read_prompt_file(file_path: str) -> list[Prompt]

This function reads newline-delimited prompts from disk.

Behavior:
- supports convenience resolution from prompts.txt to inputs/prompts.txt.
- raises MissingPromptFile if path does not exist.
- raises WrongPromptFile if no non-empty lines exist.

### write_jsonl(listings, output_path)

This function writes listings to JSONL output.

Behavior:
- overwrites target file.
- writes one JSON object per line.

### _safe_text(locator) -> str

This helper safely reads text from a Playwright locator.

Behavior:
- returns empty string for missing locator.
- returns stripped text for matching locator.

### _safe_attr(locator, attr, timeout=None) -> str

This helper safely reads an attribute from a locator.

Behavior:
- returns empty string for missing locator or extraction error.
- supports optional timeout.

## Extension guidance

When you create a new scraper implementation:

1. Subclass BaseScraper.
2. Implement scrape only.
3. Reuse safe helpers for resilient field extraction.
4. Keep run/checkpoint behavior in the base class unchanged unless you are
   intentionally redesigning orchestration.

## Next steps

If you modify orchestration behavior, validate with concurrency and checkpoint
focused tests before merging.

# Google Maps business listing utility

This project reads search prompts, scrapes Google Maps listing data, and writes
normalized records to `jsonl`.

The current implementation focuses on reliability for dynamic pages, duplicate
prevention, and maintainable module boundaries.

## What it does

The scraper:

- reads newline-delimited prompts from a text file
- searches each prompt on Google Maps
- lazily loads result cards
- extracts listing details from dedicated place pages
- deduplicates listings with `name + lat + lon + website_host`
- writes output in JSONL format

## Requirements

- Python 3.10+
- Playwright Python package
- Playwright browser binaries

## Setup

1. Create and activate a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Install Playwright browsers.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
```

## Run
Run the provided driver:

```bash
python task_driver.py
```

The driver runs built-in checks and writes output to `output.jsonl`.

By default, `BaseScraper.run()` enables checkpoint persistence and progress
reporting even when you do not pass a `Checkpoint` instance.

Browser mode defaults to headless and can be overridden with
`SCRAPER_HEADLESS=0` for debugging.

## Concurrency

Prompt processing supports bounded concurrency. By default, runs are
single-threaded at one prompt at a time.

Set `SCRAPER_MAX_CONCURRENCY` to increase parallel prompt workers:

```bash
SCRAPER_MAX_CONCURRENCY=3 python task_driver.py
```

## Environment variables

This project reads runtime settings from environment variables. Start from
`.env.example` and adjust values for your local runs.

The `task` package loads `.env` from the repository root using
`python-dotenv` at import time, so `SCRAPER_*` values are available without
manual export.

- `SCRAPER_MAX_CONCURRENCY`: prompt worker count. Default: `1`.
- `SCRAPER_HEADLESS`: browser mode for scraper runs. Default: `1`.
- `SCRAPER_SHOW_PROGRESS`: progress display toggle when `show_progress` is not
  passed to `run()`. Default: `1`.
- `SCRAPER_CHECKPOINT_ENABLED`: implicit checkpoint persistence toggle for
	`run()` when no explicit `Checkpoint` is passed. Default: `1`.
- `SCRAPER_CHECKPOINT_RESUME`: skip prompts already marked `succeeded` in
  checkpoint status journal. Default: `1`.
- `SCRAPER_CHECKPOINT_RESET`: remove checkpoint output and status files before
  run. Default: `0`.
- `SCRAPER_CHECKPOINT_PATH`: implicit checkpoint output path. Default:
	`output.jsonl`.

Example:

```bash
cp .env.example .env
python task_driver.py
```

Notes:

- This setting controls concurrent prompt workers.
- Deduplication remains global across workers.
- Checkpoint writes are synchronized so output and status journals stay
	consistent.
- Start with small values (for example, 2 to 4) to reduce anti-bot risk.

## Resumable runs

You can wire resumable execution by passing a `Checkpoint` instance to
`scraper.run(...)`.

Default behavior without an explicit checkpoint:

- listings are still checkpoint-persisted incrementally.
- completed prompts are skipped on rerun.

To force a fresh run against the same checkpoint path, set
`SCRAPER_CHECKPOINT_RESET=1`.

Explicit behavior with a `Checkpoint` instance:

- completed prompts are skipped on rerun.
- failed prompts stay retryable.

```python
from task.main import Checkpoint, MapsScraper

scraper = MapsScraper()
prompts = scraper.read_prompt_file("prompts.txt")
checkpoint = Checkpoint("output.jsonl")

# Resume from the last successful prompt.
listings = scraper.run(prompts, limit=30, checkpoint=checkpoint)
```

How it works:

- Listing records are appended to `output.jsonl` as each prompt finishes.
- Prompt lifecycle events are written to `output.jsonl.status.jsonl`.
- On restart, only prompts with status `succeeded` are skipped.
- Prompts with status `failed` stay retryable on the next run.

When you use checkpoint mode, you do not need to call `write_jsonl()` after
`run()`, because data is already persisted incrementally.

## Data model

Two dataclasses represent the core schema:

- `Prompt(query)`
- `Listing(name, lat, lon, url, address, website, rating, phone, query)`

## Module structure

Code is split by responsibility:

- `task/models.py`: `Prompt` and `Listing` dataclasses
- `task/error.py`: custom exception hierarchy
- `task/logger.py`: centralized logger factory
- `task/base.py`: `BaseScraper` abstract base (sync entry-point, I/O helpers)
- `task/scraper.py`: `MapsScraper` — Google Maps extraction logic
- `task/checkpoint.py`: `Checkpoint` — append-only JSONL status journal
- `task/progress.py`: `ProgressReporter` — Rich/plain terminal progress display
- `task/retries.py`: `RetryConfig` and `retry_with_backoff` decorator
- `task/normalizers/listing.py`: `ListingNormalizer` — field cleaning and dedup key
- `task/main.py`: backward-compatible re-exports
- `task/__init__.py`: package exports

`task_driver.py` still imports from `task.main`, and compatibility is preserved.

## Maintainer documentation

This repository uses a non-overlapping documentation layout:

- Architecture and maintenance workflows: `docs/MAINTAINER_GUIDE.md`
- New contributor quick start: `docs/DEVELOPER_ONBOARDING.md`
- Class and function API reference: `docs/modules/overview.md`

## Error handling

Custom errors are defined in `task/error.py`:

- `ScraperError`: base class
- `MissingPromptFile`: raised when prompt file path does not exist
- `WrongPromptFile`: raised when prompt file has no usable lines

Each error includes the source file path in its message.

## Logging

Logging is configured in `task/logger.py` and used by the scraper.

- logger name: `task.scraper`
- default level: `INFO`
- output format: timestamp, level, logger name, message

Current logs include feed-detection status, per-prompt listing counts, and
exception traces.

## Notes on extraction reliability

To reduce stale UI-state issues, the scraper follows a two-stage approach:

1. Collect candidate place URLs from the search results list.
2. Open each place URL in a dedicated details page for field extraction.

This approach is slower than direct card clicking but more consistent for
dynamic UI updates.

Failed detail-page extractions are retried up to three times with exponential
back-off and jitter before the listing is skipped and the prompt continues.

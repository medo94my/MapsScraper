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
- deduplicates listings with `name + lat + lon`
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

**Optional:** For rich terminal formatting during scraper runs, uncomment the `rich` line in `requirements.txt` and reinstall:

```bash
pip install rich
```

## Container setup

You can build and run the scraper in Docker when you want a reproducible local
environment with Playwright and Chromium preinstalled.

Build the image from the repository root:

```bash
docker build -t maps-scraper .
```

Run the driver in the container:

```bash
docker run --rm -it maps-scraper
```

If you want the generated `output.jsonl` and any input edits to persist directly
in your working tree, run the container with a bind mount:

```bash
docker run --rm -it -v "$PWD:/app" maps-scraper
```

The image sets `SCRAPER_HEADLESS=1`, so the fixed `task_driver.py` contract can
run in a container without needing a display server.

## Run

Run the provided driver:

```bash
python task_driver.py
```

The driver runs built-in checks and writes output to `output.jsonl`.

## Resumable runs

You can wire resumable execution by passing a `Checkpoint` instance to
`scraper.run(...)`.

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

- `task/models.py`: `Prompt` and `Listing`
- `task/error.py`: custom exception hierarchy
- `task/logger.py`: centralized logger factory
- `task/scraper.py`: `MapsScraper` implementation
- `task/main.py`: backward-compatible re-exports
- `task/__init__.py`: package exports

`task_driver.py` still imports from `task.main`, and compatibility is preserved.

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

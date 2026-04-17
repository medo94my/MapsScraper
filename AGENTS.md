# Agent Instructions

This is a Google Maps business listing scraper. The driver contract (`task_driver.py`) is **fixed** — do not modify it. All logic lives in the `task/` package.

## Environment setup

```bash
python -m venv venv
source venv/bin/activate
pip install playwright
playwright install chromium
```

## Run & verify

```bash
python task_driver.py      # runs built-in tests then writes output.jsonl
```

Exit code 0 = success. The driver runs four checks before the main scrape — a failing check calls `sys.exit(-1)`.

## Package structure

| File | Responsibility |
|---|---|
| `task/models.py` | `Prompt` and `Listing` dataclasses — single source of truth for the schema |
| `task/error.py` | `ScraperError`, `MissingPromptFile`, `WrongPromptFile` |
| `task/logger.py` | `get_logger(name)` factory — always use this, never `print()` |
| `task/base.py` | `BaseScraper` — abstract base with `run()`, `read_prompt_file()`, `write_jsonl()`, `_safe_text()`, `_safe_attr()` |
| `task/checkpoint.py` | `Checkpoint` — prompt-level append-only JSONL checkpoint with status journal |
| `task/progress.py` | `ProgressReporter` — optional Rich-based terminal progress display (graceful fallback to plain text if Rich not installed) |
| `task/scraper.py` | `MapsScraper(BaseScraper)` — all Google Maps-specific logic |
| `task/main.py` | Backward-compat re-exports for `from task.main import *` |
| `task/__init__.py` | Package-level exports |

## Key conventions

- **New scrapers** must subclass `BaseScraper` and implement `async scrape(prompts, limit) -> list[Listing]`.
- **Never add** `run()`, `read_prompt_file()`, `write_jsonl()`, `_safe_text()`, or `_safe_attr()` to a subclass — they are inherited from `BaseScraper`.
- **Logging**: use `get_logger("task.<module>")` at module level, not `print()`.
- **Errors**: raise `MissingPromptFile` / `WrongPromptFile` (both subclass `ScraperError`) for prompt file problems.
- **Deduplication key**: `f"{listing.name}_{listing.lat}_{listing.lon}"` — maintain this across prompts via `global_seen_keys`.
- **`Listing.query`** must be set to the originating `Prompt.query` — required for checkpointing and traceability.

## Checkpointing

Pass a `Checkpoint` instance to `scraper.run()` for resumable runs:

```python
from task import Checkpoint, MapsScraper
checkpoint = Checkpoint("output.jsonl")
listings = scraper.run(prompts, limit=30, checkpoint=checkpoint)
# write_jsonl is not needed — checkpoint already wrote to disk
```

## Progress reporting

When running with checkpoint mode, progress is displayed in the terminal by default using `ProgressReporter`.

```python
# Progress display is on by default in checkpoint mode
listings = scraper.run(prompts, limit=30, checkpoint=checkpoint, show_progress=True)

# Turn it off if needed
listings = scraper.run(prompts, limit=30, checkpoint=checkpoint, show_progress=False)
```

Progress includes:
- Per-prompt lifecycle: started → extracted → completed (or failed)
- Status emojis: `→` (started), `✓` (extracted/completed), `✗` (failed)
- End-of-run summary: total prompts, skipped, completed, failed, total listings, success rate, elapsed time

Rich formatting is used if installed (`pip install rich`); otherwise falls back to plain text logging.

Two-stage to avoid stale live-list state:
1. Collect `href` candidates from the search results feed (adaptive scroll loop, up to 40 rounds, stops on 5 stagnant rounds).
2. Navigate each `href` in a dedicated `detail_page` and extract fields from `div[role="main"]:visible` filtered by `h1.DUwDvf`.

## Gitignored files

`output.jsonl`, `inputs/`, `venv/`, `TODO.md`, `IMPLEMENTATION_PLAN*.md` are gitignored — do not commit them.

## Reference

- [README.md](README.md) — setup, data model, module overview, extraction notes
- [task_driver.py](task_driver.py) — fixed driver contract with test cases

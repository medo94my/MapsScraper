# Maintainer guide

This guide is the architecture and operations hub for maintaining the Google
Maps business listing scraper. It explains system behavior, ownership
boundaries, and change workflows.

For class-by-class and function-by-function API reference, use the module pages
in [docs/modules/overview.md](docs/modules/overview.md). That module set is the
single source of truth for API details.

## Documentation layout policy

This repository uses a strict documentation split to avoid duplicate and stale
content.

- [docs/DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md): quick ramp-up.
- [docs/MAINTAINER_GUIDE.md](docs/MAINTAINER_GUIDE.md): architecture,
  operations, and maintenance workflows.
- [docs/modules/overview.md](docs/modules/overview.md): API reference entry
  point.
- [docs/modules/*.md](docs/modules/overview.md): class and function details.

Policy rules:
- API signatures and function behavior must be documented only in module pages.
- This maintainer guide must not duplicate class or function API details.
- Onboarding docs must focus on setup and first contributions only.

## System responsibilities

The scraper system reads prompt queries, extracts Google Maps listing data,
normalizes records, deduplicates across prompts, and writes JSONL output.

Reliability is provided by:
- safe field extraction helpers
- retry for timeout-prone detail extraction
- prompt-level checkpoint status journaling
- resumable processing in explicit checkpoint mode
- progress reporting with Rich fallback

## Runtime flow

Use this sequence when reasoning about behavior and debugging regressions.

1. Prompt input is parsed into Prompt objects.
2. BaseScraper.run selects normal mode or checkpoint mode.
3. MapsScraper.scrape processes prompts and extracts listing candidates.
4. Listing normalization and dedupe key generation are applied.
5. Output is written either incrementally by implicit or explicit checkpoint
   mode, or as one final write when checkpointing is disabled.

By default, BaseScraper.run enables checkpoint persistence through environment
configuration even when callers do not pass a Checkpoint instance.

## Module ownership map

Use this map to locate the correct place for code changes.

- Data contracts: [task/models.py](task/models.py)
- Prompt validation and sync orchestration:
  [task/base.py](task/base.py)
- Google Maps extraction logic: [task/scraper.py](task/scraper.py)
- Retry policy: [task/retries.py](task/retries.py)
- Checkpoint state and journals: [task/checkpoint.py](task/checkpoint.py)
- Progress reporting: [task/progress.py](task/progress.py)
- Normalization and dedupe identity:
  [task/normalizers/listing.py](task/normalizers/listing.py)
- Logging setup: [task/logger.py](task/logger.py)
- Backward-compatible exports: [task/main.py](task/main.py)

## Non-negotiable invariants

These invariants protect correctness and resume safety.

- Do not change the driver contract in [task_driver.py](task_driver.py).
- Keep Listing query traceability from originating prompt to persistence.
- Keep failed prompts retryable in checkpoint mode.
- Preserve append-only status journaling semantics.
- Preserve global deduplication across prompts in a run.
- Keep extraction resilient to missing optional fields.

## Change workflows

Use the workflow that matches your change type.

### Selector or extraction updates

1. Update selectors and extraction fallback behavior in
   [task/scraper.py](task/scraper.py).
2. Confirm normalization still produces stable values in
   [task/normalizers/listing.py](task/normalizers/listing.py).
3. Run tests and then run the driver end to end.

### Data schema updates for Listing

1. Update Listing fields in [task/models.py](task/models.py).
2. Update extraction construction path in [task/scraper.py](task/scraper.py).
3. Update normalization in [task/normalizers/listing.py](task/normalizers/listing.py).
4. Update tests and verify output JSONL shape.

### Deduplication logic updates

1. Modify dedupe behavior in
   [task/normalizers/listing.py](task/normalizers/listing.py).
2. Validate duplicate collapse behavior with tests and fixture cases.
3. Document behavior changes in the module reference page.

### Checkpoint lifecycle updates

1. Update event behavior in [task/checkpoint.py](task/checkpoint.py).
2. Validate skip, failed, and resume semantics through rerun scenarios.
3. Preserve backward compatibility for existing journal files.

## Verification checklist

Run this checklist before merging scraper changes.

1. Run test suite and fix regressions.
2. Run end-to-end driver flow and confirm exit code 0.
3. Inspect output and status journals for expected lifecycle behavior.
4. Confirm exports remain compatible for existing imports.
5. Confirm docs were updated in the correct layer:
   - architecture and workflow in this guide
   - API detail only in module reference pages

## Runbook commands

Use these commands during maintenance.

Use `.env.example` as the source of supported runtime environment variables.

```bash
python -m pytest tests/ -v
python task_driver.py
SCRAPER_HEADLESS=0 python task_driver.py
SCRAPER_SHOW_PROGRESS=0 python task_driver.py
SCRAPER_MAX_CONCURRENCY=3 python task_driver.py
SCRAPER_CHECKPOINT_ENABLED=0 python task_driver.py
SCRAPER_CHECKPOINT_PATH=output/output.jsonl python task_driver.py
```

## Known tradeoffs

Current design intentionally favors stability over maximum throughput.

- Prompt-level checkpoint orchestration is simple and robust.
- Selector strategy may need periodic updates when Maps UI changes.
- Dedupe identity balances false positives against incomplete websites.

## Next steps

If you are new to this codebase:

1. Start with [docs/DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md).
2. Read [docs/modules/overview.md](docs/modules/overview.md).
3. Trace one prompt from input parsing to output write.

If you are preparing a non-trivial refactor:

1. Write the intended invariants in your pull request description.
2. Update affected module reference pages first.
3. Run tests and end-to-end validation before review.

# Developer onboarding guide

This guide gets you productive in this repository quickly. You will learn how to
run the scraper, understand the runtime flow, locate key modules, and make safe
changes without breaking the driver contract.

Use this page for onboarding. Use the maintainer and module reference pages for
full API details.

## What you are maintaining

This project scrapes Google Maps business listings from prompt queries and
writes normalized JSONL output. Reliability is built through retries,
checkpointing, normalization, and prompt-level progress reporting.

The fixed integration contract is in task_driver.py. You can change code inside
 task/, but you must not change task_driver.py.

## First run in ten minutes

Follow these steps to set up and verify the project behavior on your machine.

1. Create and activate a virtual environment.
2. Install Python dependencies.
3. Install Playwright Chromium.
4. Run the driver.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python task_driver.py
```

If the command exits with code 0, the baseline flow is healthy.

## Daily development workflow

Use this repeatable loop when you modify scraper behavior.

1. Run tests before changes to confirm baseline.
2. Make focused edits in task/.
3. Run tests again.
4. Run task_driver.py for end-to-end verification.
5. Inspect output and status JSONL files for regressions.

```bash
python -m pytest tests/ -v
python task_driver.py
```

## Runtime architecture at a glance

The runtime path is stable and is the main concept you need to preserve during
maintenance.

1. Prompt loading: BaseScraper.read_prompt_file reads newline-delimited queries.
2. Orchestration: BaseScraper.run decides normal mode or checkpoint mode.
3. Scraping: MapsScraper.scrape processes prompts and collects listings.
4. Extraction: _scrape_single_prompt and _extract_listing_from_href parse Maps
   pages.
5. Normalization and dedupe: ListingNormalizer standardizes fields and builds
   dedupe keys.
6. Persistence: BaseScraper.write_jsonl or Checkpoint.save_listings writes
   records.

## Core files you should know first

Start with these modules in order. This order matches how data flows at runtime.

- task/models.py: Prompt and Listing contracts.
- task/base.py: base runtime and checkpoint orchestration.
- task/scraper.py: Google Maps extraction logic.
- task/normalizers/listing.py: field normalization and dedupe identity.
- task/checkpoint.py: resumable progress and status events.
- task/progress.py: terminal progress and summary reporting.
- task/retries.py: retry decorator and policy config.

## Data model essentials

Prompt carries one query string. Listing is the shared payload that moves across
scraping, normalization, deduplication, checkpoint writes, and tests.

Critical rule:
- Keep Listing.query populated with the originating prompt query.

If query traceability breaks, checkpoint status and debugging quality degrade.

## Reliability design you must preserve

The codebase includes reliability patterns that protect long scraping runs.

- Prompt-level checkpointing: completed prompts are skipped on rerun.
- Failed prompts stay retryable: failures are recorded but not terminal.
- Incremental persistence: listings are flushed per prompt in checkpoint mode.
- Timeout retry: detail extraction retries on transient timeout failures.
- Safe extraction helpers: missing selectors return empty strings instead of
  crashing the run.

## Safe change boundaries

This section tells you where changes are usually safe and where caution is
required.

Safe to change:
- Selector tuning and extraction fallbacks in task/scraper.py.
- Normalization rules in task/normalizers/listing.py.
- Logging verbosity and message clarity.
- Retry policy values in task/retries.py.

Change carefully:
- Dedupe key structure in ListingNormalizer.dedupe_key.
- Checkpoint journal schema in task/checkpoint.py.
- Export surfaces in task/main.py and task/__init__.py.
- Control flow in BaseScraper.run and _run_with_checkpoint_async.

Do not change:
- task_driver.py contract and behavior.

## Common maintenance tasks

Use these patterns for frequent tasks.

### Add a new extracted field

This task requires coordinated changes across model, extraction, normalization,
and tests.

1. Add the field to Listing in task/models.py.
2. Extract the field in _extract_listing_from_href.
3. Normalize the field in normalize_listing.
4. Ensure JSONL writing includes the field.
5. Update or add tests.

### Update a broken selector

This task is common when Google Maps UI changes.

1. Update selector in task/scraper.py.
2. Keep fallback behavior so missing fields do not crash runs.
3. Validate with task_driver.py.
4. Check listing counts and field population.

### Tune runtime speed and stability

This task balances anti-bot risk and throughput.

1. Start with SCRAPER_MAX_CONCURRENCY at 1.
2. Increase gradually to 2 to 4 in local testing.
3. Watch failure rate, retries, and extracted listings.
4. Keep settings conservative for production-like runs.

## Troubleshooting quick map

Use this table when triaging issues.

| Symptom | Likely location | First action |
|---|---|---|
| Prompt file errors | task/base.py, task/error.py | Validate path and file contents |
| Empty or low extraction | task/scraper.py selectors | Re-check feed and detail selectors |
| Duplicate records | task/normalizers/listing.py | Inspect dedupe_key changes |
| Resume skips unexpectedly | task/checkpoint.py | Inspect status journal states |
| Excessive timeout failures | task/retries.py, task/scraper.py | Tune timeouts and retry policy |

## Documentation map

After this onboarding page, use the detailed docs below.

- docs/MAINTAINER_GUIDE.md for full architecture and contracts.
- docs/modules/overview.md for module-level reference index.
- docs/modules/*.md for class and function details by module.

## Next steps

Once you finish this guide, do the following to build confidence.

1. Run the project end to end once.
2. Read the module overview page.
3. Pick one module and trace one prompt from input to output.
4. Make a small non-functional change and verify tests plus driver run.

# Checkpoint reference

This page documents resumable persistence behavior for long scraper runs.
Checkpoint design is append-only and prompt-centric, which supports safe resume
and minimal progress loss on interruption.

## Module purpose

task/checkpoint.py stores prompt lifecycle states and listing rows in JSONL
journals.

## Class: Checkpoint

Checkpoint tracks prompt completion state and appends prompt results to disk.

### __init__(output_path: str)

This constructor initializes output and status journal paths and loads prior
state.

Internal files:
- output JSONL at the configured output path.
- status journal JSONL at output filename plus .status.jsonl.

### _load()

This internal function restores checkpoint state from existing files.

Behavior:
- loads status journal first.
- uses output file as fallback for older data compatibility.

### _load_status_journal()

This internal function rebuilds latest status per query from status events.

Behavior:
- parses one event per line.
- skips malformed lines with warnings.
- marks succeeded queries as completed.

### _load_output_fallback()

This internal function backfills completed prompts from output records.

Purpose:
- preserve compatibility for runs that predate status journaling.

### _append_status_event(prompt, status, reason="")

This internal function appends one lifecycle event and updates in-memory state.

Event fields:
- query
- status
- reason
- ts (UTC ISO timestamp)

### completed_queries

This property returns a read-only set of completed query strings.

### is_done(prompt: Prompt) -> bool

This function checks whether a prompt has terminal succeeded state.

### filter_prompts(prompts: list[Prompt]) -> list[Prompt]

This function filters out prompts already completed in checkpoint state.

### mark_started(prompt: Prompt)

This function writes a started event for the prompt.

### mark_succeeded(prompt: Prompt)

This function writes a succeeded event and marks prompt completed.

### mark_failed(prompt: Prompt, reason: str = "")

This function writes a failed event.

Behavior:
- failed prompts remain retryable on later runs.

### save_listings(prompt: Prompt, listings: list[Listing])

This function appends prompt listings to output JSONL.

Behavior:
- writes Listing fields and forces query from prompt.
- flushes file handle after writes for durability.

### save(prompt: Prompt, listings: list[Listing])

This compatibility helper saves listings and marks success.

## Operational notes

BaseScraper.run uses checkpoint persistence in two modes:

- Implicit mode (default when no explicit checkpoint is passed and
	`SCRAPER_CHECKPOINT_ENABLED=1`): listings are persisted incrementally and
	completed prompts are skipped by default.
- Explicit mode (caller passes Checkpoint): listings are persisted
	incrementally and completed prompts are skipped.

Path controls:

- `SCRAPER_CHECKPOINT_PATH` sets the implicit output path.
- `SCRAPER_CHECKPOINT_RESUME` controls skip-on-rerun behavior (default `1`).
- `SCRAPER_CHECKPOINT_RESET` resets output and status files before run
  (default `0`).

## Next steps

If you change status schema or event semantics, document migration impact and
keep backward compatibility explicit.

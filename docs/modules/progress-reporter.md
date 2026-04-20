# ProgressReporter reference

This page documents terminal progress reporting used during checkpoint-enabled
runs.

## Module purpose

task/progress.py tracks prompt lifecycle counters and prints prompt-level updates
plus end-of-run summary metrics.

## Class: ProgressReporter

ProgressReporter reports started, extracted, completed, and failed events.

### __init__(use_rich: bool = True)

This constructor enables Rich output when available and requested.

Behavior:
- initializes counters for started, completed, failed, and total listings.
- creates Rich console if rich is installed and use_rich is true.

### on_started(prompt: Prompt)

This function records and emits a prompt started event.

### on_extracted(prompt: Prompt, count: int)

This function emits an extraction event with listing count.

### on_completed(prompt: Prompt, count: int, elapsed_sec: float)

This function records completion counters and emits completion event text.

### on_failed(prompt: Prompt, reason: str = "")

This function records failures and emits failure event text.

### print_summary(total_prompts: int, total_elapsed_sec: float)

This function prints final run summary.

Derived metrics:
- skipped prompt count
- success rate
- average listings per completed prompt
- elapsed time

### _print_summary_rich(...)

This internal function renders summary as a Rich table.

### _print_summary_plain(...)

This internal function logs summary in plain text.

## Usage notes

ProgressReporter is created by BaseScraper checkpoint orchestration when
show_progress is enabled. It is safe in environments without rich because output
falls back to standard logging.

## Next steps

If you add new lifecycle states, update both rich and plain summary renderers so
results remain consistent.

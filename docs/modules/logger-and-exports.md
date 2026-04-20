# Logger and exports reference

This page documents logging setup and public export surfaces. These modules are
small, but they are central to project consistency and backward compatibility.

## task/logger.py

This module provides one logger factory used across the package.

### get_logger(name: str = "task")

get_logger returns a configured logger instance for the provided name.

Behavior:
- reuses existing handlers if the logger already has handlers.
- uses RichHandler when rich is available.
- falls back to standard StreamHandler when rich is unavailable.
- sets level to INFO and disables propagation.

Usage notes:
- use this function in all package modules instead of print.
- keep formatter changes centralized here to avoid drift.

Maintenance cautions:
- avoid adding duplicate handlers.
- preserve logger.propagate = False to prevent duplicate output in some
  environments.

## task/main.py

This module preserves the original import contract expected by task_driver.py.

Purpose:
- re-export core package types from a stable path.

Exported symbols:
- BaseScraper
- Checkpoint
- ProgressReporter
- ScraperError, MissingPromptFile, WrongPromptFile
- Prompt, Listing
- ListingNormalizer
- MapsScraper

Maintenance cautions:
- treat changes here as contract changes for existing integrations.

## task/__init__.py

This module provides package-level convenience exports.

Purpose:
- expose public symbols for imports from task.

Additional exported symbols:
- RetryConfig
- retry_with_backoff

Maintenance cautions:
- keep task/main.py and task/__init__.py aligned intentionally.
- if surfaces differ, document why and ensure callers are not broken.

## Next steps

If you add new public utilities, update both export modules and this page in the
same change.

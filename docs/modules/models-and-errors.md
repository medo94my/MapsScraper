# Models and errors reference

This page documents the shared data contracts and error classes used across the
scraper package. These types define the boundaries between runtime orchestration,
extraction, persistence, and tests.

## task/models.py

This module defines the two dataclasses used throughout the scraper flow.

### Prompt

Prompt represents a single search query.

Fields:
- query: str

Usage notes:
- BaseScraper.read_prompt_file creates Prompt instances from non-empty lines.
- Prompt.query is used in search URL construction and checkpoint status events.

### Listing

Listing represents one business listing record that can be persisted to JSONL.

Fields:
- name: str
- lat: float
- lon: float
- url: str
- address: str = ""
- website: str = ""
- rating: str = ""
- phone: str = ""
- query: str = ""

Usage notes:
- query must carry the originating prompt for traceability.
- optional fields can be empty when source data is unavailable.
- listing instances are normalized before dedupe and persistence.

Maintenance cautions:
- adding fields requires synchronized updates in extraction, normalization,
  writing logic, and tests.

## task/error.py

This module defines domain-specific exceptions for prompt file validation.

### ScraperError

ScraperError is the base exception type for scraper-related failures.

Usage notes:
- catch this base class when you need package-level error handling semantics.

### MissingPromptFile

MissingPromptFile is raised when the provided prompt file path does not exist.

Constructor:
- MissingPromptFile(file_path: str)

Behavior:
- stores the file path in the exception instance.
- sets a message that the prompt file is missing.

### WrongPromptFile

WrongPromptFile is raised when the prompt file has no usable prompt lines.

Constructor:
- WrongPromptFile(file_path: str)

Behavior:
- stores the file path in the exception instance.
- sets a message that the prompt file is empty or invalid.

## Next steps

If you change these contracts, update tests and module references that use these
objects before merging.

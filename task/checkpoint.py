#!/usr/bin/env python3
"""Checkpoint — prompt-level persistence for resumable scraper runs.

Usage::

    checkpoint = Checkpoint("output.jsonl")

    # Filter already-done prompts before starting
    remaining = checkpoint.filter_prompts(all_prompts)

    for prompt in remaining:
        listings = await scrape_one(prompt)
        # Persist immediately — safe even if the process crashes after this line
        checkpoint.save(prompt, listings)

On the next run, ``filter_prompts`` skips only prompts with a terminal
``succeeded`` status in the status journal, so failed prompts remain
retryable.
"""
import json
import pathlib
from datetime import datetime, timezone

from task.logger import get_logger
from task.models import Listing, Prompt


logger = get_logger("task.checkpoint")


class Checkpoint:
    """Prompt-level checkpoint backed by an append-only JSONL file.

    Each call to :meth:`save` immediately flushes completed listings to disk,
    so a crash between prompts never loses work that has already been written.
    On the next run, :meth:`filter_prompts` skips only prompts with a
    ``succeeded`` status in the status journal.
    """

    def __init__(self, output_path: str) -> None:
        self._path = pathlib.Path(output_path)
        self._status_path = self._path.with_name(f"{self._path.name}.status.jsonl")
        self._completed: set[str] = set()
        self._status: dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Populate checkpoint state from status and output files, if any."""
        self._load_status_journal()
        self._load_output_fallback()

        logger.info(
            "Checkpoint loaded — %d succeeded prompt(s), %d tracked status prompt(s)",
            len(self._completed),
            len(self._status),
        )

    def _load_status_journal(self) -> None:
        """Load prompt lifecycle events from the status journal."""
        if not self._status_path.exists():
            logger.info("No status journal at %s — starting fresh", self._status_path)
            return

        with self._status_path.open(encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                    query = event.get("query", "")
                    status = event.get("status", "")
                    if query and status:
                        self._status[query] = status
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping malformed status line %d in %s",
                        lineno,
                        self._status_path,
                    )

        self._completed = {q for q, st in self._status.items() if st == "succeeded"}

    def _load_output_fallback(self) -> None:
        """Backfill completed prompts from output data when no status exists.

        This keeps existing users of the old format compatible during migration.
        """
        if not self._path.exists():
            logger.info("No existing checkpoint at %s — starting fresh", self._path)
            return

        with self._path.open(encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                    query = record.get("query", "")
                    if query and query not in self._status:
                        self._completed.add(query)
                        self._status[query] = "succeeded"
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed line %d in %s", lineno, self._path)

    def _append_status_event(self, prompt: Prompt, status: str, reason: str = "") -> None:
        """Append a status event for one prompt and update in-memory status."""
        event = {
            "query": prompt.query,
            "status": status,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        with self._status_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
            fh.flush()

        self._status[prompt.query] = status
        if status == "succeeded":
            self._completed.add(prompt.query)
        elif prompt.query in self._completed:
            self._completed.remove(prompt.query)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def completed_queries(self) -> frozenset[str]:
        """Read-only view of queries that have already been checkpointed."""
        return frozenset(self._completed)

    def is_done(self, prompt: Prompt) -> bool:
        """Return ``True`` if *prompt* has already been saved to the checkpoint."""
        return prompt.query in self._completed

    def filter_prompts(self, prompts: list[Prompt]) -> list[Prompt]:
        """Return only prompts that are not in terminal ``succeeded`` state."""
        remaining = [p for p in prompts if not self.is_done(p)]
        skipped = len(prompts) - len(remaining)
        if skipped:
            logger.info("Skipping %d already-completed prompt(s)", skipped)
        return remaining

    def mark_started(self, prompt: Prompt) -> None:
        """Record that processing for *prompt* has started."""
        self._append_status_event(prompt, "started")

    def mark_succeeded(self, prompt: Prompt) -> None:
        """Record that processing for *prompt* succeeded."""
        self._append_status_event(prompt, "succeeded")

    def mark_failed(self, prompt: Prompt, reason: str = "") -> None:
        """Record that processing for *prompt* failed and stays retryable."""
        self._append_status_event(prompt, "failed", reason=reason)

    def save_listings(self, prompt: Prompt, listings: list[Listing]) -> None:
        """Append *listings* for *prompt* to the JSONL file.

        The file is opened in append mode and flushed after every write, so
        partial progress survives a crash between calls.
        """
        with self._path.open("a", encoding="utf-8") as fh:
            for listing in listings:
                record = {**listing.__dict__, "query": prompt.query}
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()

        logger.info(
            "Checkpointed %d listing(s) for prompt '%s'",
            len(listings),
            prompt.query,
        )

    def save(self, prompt: Prompt, listings: list[Listing]) -> None:
        """Backward-compatible helper: persist listings and mark prompt success."""
        self.save_listings(prompt, listings)
        self.mark_succeeded(prompt)

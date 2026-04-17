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

On the next run, ``filter_prompts`` will skip any prompt whose query already
appears in the JSONL file, so only failed or unseen prompts are retried.
"""
import json
import pathlib

from task.logger import get_logger
from task.models import Listing, Prompt


logger = get_logger("task.checkpoint")


class Checkpoint:
    """Prompt-level checkpoint backed by an append-only JSONL file.

    Each call to :meth:`save` immediately flushes completed listings to disk,
    so a crash between prompts never loses work that has already been written.
    On the next run, :meth:`filter_prompts` skips any query already present in
    the file.
    """

    def __init__(self, output_path: str) -> None:
        self._path = pathlib.Path(output_path)
        self._completed: set[str] = set()
        self._load()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Populate ``_completed`` from an existing JSONL file, if any."""
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
                    if query:
                        self._completed.add(query)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed line %d in %s", lineno, self._path)

        logger.info(
            "Checkpoint loaded — %d completed prompt(s) from %s",
            len(self._completed),
            self._path,
        )

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
        """Return only the prompts that have **not** yet been checkpointed."""
        remaining = [p for p in prompts if not self.is_done(p)]
        skipped = len(prompts) - len(remaining)
        if skipped:
            logger.info("Skipping %d already-completed prompt(s)", skipped)
        return remaining

    def save(self, prompt: Prompt, listings: list[Listing]) -> None:
        """Append *listings* for *prompt* to the JSONL file and mark it done.

        The file is opened in append mode and flushed after every write, so
        partial progress survives a crash between calls.
        """
        with self._path.open("a", encoding="utf-8") as fh:
            for listing in listings:
                record = {**listing.__dict__, "query": prompt.query}
                fh.write(json.dumps(record) + "\n")
            fh.flush()

        self._completed.add(prompt.query)
        logger.info(
            "Checkpointed %d listing(s) for prompt '%s'",
            len(listings),
            prompt.query,
        )

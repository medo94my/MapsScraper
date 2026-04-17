#!/usr/bin/env python3
"""Abstract base class for all scrapers in the task package.

Concrete scrapers must implement the ``scrape`` coroutine.  All other shared
infrastructure (sync entry-point, prompt I/O, JSONL output, and Playwright
locator helpers) lives here so that new scrapers only need to provide the
site-specific extraction logic.
"""
import asyncio
import json
import os
import pathlib
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterable, Optional

from task.error import MissingPromptFile, WrongPromptFile
from task.logger import get_logger
from task.models import Listing, Prompt
from task.progress import ProgressReporter

if TYPE_CHECKING:
    from task.checkpoint import Checkpoint


logger = get_logger("task.base")


class BaseScraper(ABC):
    """Abstract base for Playwright-based scrapers.

    Subclasses must implement :meth:`scrape`.
    """

    def __init__(
        self,
        headless: bool = True,
        max_concurrency: int | None = None,
    ) -> None:
        self.headless = headless
        if max_concurrency is None:
            max_concurrency = self._env_int("SCRAPER_MAX_CONCURRENCY", default=1)
        self.max_concurrency = max(1, max_concurrency)

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        value = os.getenv(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning("Invalid %s value '%s'; falling back to %s", name, value, default)
            return default

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def scrape(self, prompts: list[Prompt], limit: int) -> list[Listing]:
        """Run the scraper for *prompts* and return up to *limit* listings each."""

    # ------------------------------------------------------------------
    # Sync entry-point
    # ------------------------------------------------------------------

    def run(
        self,
        prompts: Iterable[Prompt],
        limit: int = 10,
        checkpoint: Optional["Checkpoint"] = None,
        show_progress: bool = True,
    ) -> list[Listing]:
        """Synchronous wrapper around :meth:`scrape` for use outside async contexts.

        When *checkpoint* is provided the run is resumable: already-completed
        prompts are skipped and each prompt's results are flushed to disk
        immediately after it finishes, so a crash loses at most one prompt's
        worth of work.

        When *show_progress* is True, progress is displayed in the terminal
        (Rich-formatted if available, plain text otherwise).
        """
        prompts_list = list(prompts)
        if not prompts_list:
            return []

        if checkpoint is not None:
            return self._run_with_checkpoint(
                prompts_list, limit, checkpoint, show_progress
            )

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.scrape(prompts_list, limit))
        except Exception:
            logger.exception("An error occurred during scraping")
            return []

    def _run_with_checkpoint(
        self,
        prompts: list[Prompt],
        limit: int,
        checkpoint: "Checkpoint",
        show_progress: bool = True,
    ) -> list[Listing]:
        """Process prompts with checkpoint lifecycle events and bounded concurrency."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                self._run_with_checkpoint_async(
                    prompts=prompts,
                    limit=limit,
                    checkpoint=checkpoint,
                    show_progress=show_progress,
                )
            )
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _run_with_checkpoint_async(
        self,
        prompts: list[Prompt],
        limit: int,
        checkpoint: "Checkpoint",
        show_progress: bool = True,
    ) -> list[Listing]:
        """Async checkpoint worker that runs prompts with bounded concurrency."""
        remaining = checkpoint.filter_prompts(prompts)
        if not remaining:
            logger.info("All prompts already checkpointed — nothing to do")
            return []

        all_listings: list[Listing] = []
        reporter = ProgressReporter(use_rich=True) if show_progress else None
        run_start_time = time.time()

        checkpoint_lock = asyncio.Lock()
        reporter_lock = asyncio.Lock()
        listings_lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def process_prompt(prompt: Prompt) -> None:
            async with semaphore:
                async with checkpoint_lock:
                    checkpoint.mark_started(prompt)

                if reporter:
                    async with reporter_lock:
                        reporter.on_started(prompt)

                prompt_start = time.time()
                try:
                    batch = await self.scrape([prompt], limit)

                    async with checkpoint_lock:
                        checkpoint.save_listings(prompt, batch)
                        checkpoint.mark_succeeded(prompt)

                    if reporter:
                        elapsed = time.time() - prompt_start
                        async with reporter_lock:
                            reporter.on_extracted(prompt, len(batch))
                            reporter.on_completed(prompt, len(batch), elapsed)
                except Exception:
                    logger.exception("Failed to scrape prompt '%s' — skipping", prompt.query)
                    async with checkpoint_lock:
                        checkpoint.mark_failed(prompt, reason="scrape_exception")
                    if reporter:
                        async with reporter_lock:
                            reporter.on_failed(prompt, reason="scrape_exception")
                    batch = []

                async with listings_lock:
                    all_listings.extend(batch)

        await asyncio.gather(*(process_prompt(prompt) for prompt in remaining))

        if reporter:
            total_elapsed = time.time() - run_start_time
            reporter.print_summary(len(prompts), total_elapsed)

        return all_listings

    # ------------------------------------------------------------------
    # Prompt I/O helpers
    # ------------------------------------------------------------------

    def read_prompt_file(self, file_path: str) -> list[Prompt]:
        """Read newline-delimited prompts from *file_path*.

        Raises :class:`~task.error.MissingPromptFile` when the file does not
        exist and :class:`~task.error.WrongPromptFile` when it is empty.
        """
        prompt_path = pathlib.Path(file_path)

        # Convenience: if the caller passes "prompts.txt" and the file lives
        # under an "inputs/" sub-directory, resolve it automatically.
        if not prompt_path.exists() and prompt_path.name == "prompts.txt":
            candidate = prompt_path.parent / "inputs" / "prompts.txt"
            if candidate.exists():
                prompt_path = candidate

        if not prompt_path.exists():
            raise MissingPromptFile(file_path)

        raw = prompt_path.read_text().splitlines()
        prompts = [Prompt(query=line) for line in raw if line.strip()]
        if not prompts:
            raise WrongPromptFile(file_path)
        return prompts

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def write_jsonl(self, listings: Iterable[Listing], output_path: str) -> None:
        """Write *listings* to a JSON Lines file at *output_path*."""
        with open(output_path, "w", encoding="utf-8") as fh:
            for listing in listings:
                fh.write(json.dumps(listing.__dict__, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Playwright locator helpers (generic, reusable by any subclass)
    # ------------------------------------------------------------------

    async def _safe_text(self, locator) -> str:
        """Return trimmed text content, or ``""`` when the locator has no match."""
        if await locator.count() == 0:
            return ""
        value = await locator.text_content()
        return (value or "").strip()

    async def _safe_attr(self, locator, attr: str, timeout: int | None = None) -> str:
        """Return an attribute value with a guarded timeout to avoid hard failures."""
        if await locator.count() == 0:
            return ""
        try:
            kwargs = {"timeout": timeout} if timeout is not None else {}
            value = await locator.get_attribute(attr, **kwargs)
            return (value or "").strip()
        except Exception:
            return ""

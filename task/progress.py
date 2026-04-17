#!/usr/bin/env python3
"""Progress reporting for scraper runs using Rich (optional).

If Rich is not installed, falls back to standard logging.
"""
import time
from datetime import timedelta
from typing import Optional

from task.logger import get_logger
from task.models import Prompt

logger = get_logger("task.progress")

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class ProgressReporter:
    """Track and report on scraper progress with optional Rich formatting.

    Usage:
        reporter = ProgressReporter(use_rich=True)
        reporter.on_started(prompt)
        reporter.on_extracted(prompt, count)
        reporter.on_completed(prompt, count, elapsed_sec)
        reporter.on_failed(prompt, reason)
        reporter.print_summary(total_prompts, total_elapsed_sec)
    """

    def __init__(self, use_rich: bool = True) -> None:
        self.use_rich = use_rich and HAS_RICH
        self.console = Console() if self.use_rich else None

        self.started_count = 0
        self.completed_count = 0
        self.failed_count = 0
        self.total_listings = 0
        self.start_time = time.time()

    def on_started(self, prompt: Prompt) -> None:
        """Report that a prompt has started processing."""
        self.started_count += 1
        msg = f"[→] Started: {prompt.query}"
        if self.use_rich:
            self.console.print(Text(msg, style="cyan"))
        else:
            logger.info(msg)

    def on_extracted(self, prompt: Prompt, count: int) -> None:
        """Report that listings have been extracted for a prompt."""
        msg = f"[✓] Extracted {count} listing(s): {prompt.query}"
        if self.use_rich:
            self.console.print(Text(msg, style="green"))
        else:
            logger.info(msg)

    def on_completed(self, prompt: Prompt, count: int, elapsed_sec: float) -> None:
        """Report that a prompt has completed successfully."""
        self.completed_count += 1
        self.total_listings += count
        elapsed_str = f"{elapsed_sec:.2f}s"
        msg = f"[✓] Completed: {prompt.query} ({count} items, {elapsed_str})"
        if self.use_rich:
            self.console.print(Text(msg, style="green bold"))
        else:
            logger.info(msg)

    def on_failed(self, prompt: Prompt, reason: str = "") -> None:
        """Report that a prompt has failed."""
        self.failed_count += 1
        reason_str = f" ({reason})" if reason else ""
        msg = f"[✗] Failed: {prompt.query}{reason_str}"
        if self.use_rich:
            self.console.print(Text(msg, style="red bold"))
        else:
            logger.error(msg)

    def print_summary(self, total_prompts: int, total_elapsed_sec: float) -> None:
        """Print a summary of the scrape run."""
        skipped_count = total_prompts - self.started_count
        success_rate = (
            100.0 * self.completed_count / total_prompts if total_prompts > 0 else 0
        )
        avg_listings = (
            self.total_listings / self.completed_count
            if self.completed_count > 0
            else 0
        )

        if self.use_rich:
            self._print_summary_rich(
                total_prompts,
                skipped_count,
                self.started_count,
                self.completed_count,
                self.failed_count,
                self.total_listings,
                success_rate,
                avg_listings,
                total_elapsed_sec,
            )
        else:
            self._print_summary_plain(
                total_prompts,
                skipped_count,
                self.started_count,
                self.completed_count,
                self.failed_count,
                self.total_listings,
                success_rate,
                avg_listings,
                total_elapsed_sec,
            )

    def _print_summary_rich(
        self,
        total_prompts: int,
        skipped_count: int,
        started_count: int,
        completed_count: int,
        failed_count: int,
        total_listings: int,
        success_rate: float,
        avg_listings: float,
        total_elapsed_sec: float,
    ) -> None:
        """Print a Rich-formatted summary table."""
        table = Table(title="Scrape Summary")

        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total prompts", str(total_prompts))
        table.add_row("Skipped (pre-existing)", str(skipped_count))
        table.add_row("Started", str(started_count))
        table.add_row("Completed", str(completed_count))
        table.add_row("Failed", str(failed_count))
        table.add_row("Total listings extracted", str(total_listings))
        table.add_row("Success rate", f"{success_rate:.1f}%")
        table.add_row("Avg listings/completed", f"{avg_listings:.1f}")
        table.add_row(
            "Elapsed time",
            str(timedelta(seconds=int(total_elapsed_sec))),
        )

        self.console.print()
        self.console.print(table)
        self.console.print()

    def _print_summary_plain(
        self,
        total_prompts: int,
        skipped_count: int,
        started_count: int,
        completed_count: int,
        failed_count: int,
        total_listings: int,
        success_rate: float,
        avg_listings: float,
        total_elapsed_sec: float,
    ) -> None:
        """Print a plain-text summary."""
        logger.info("=" * 60)
        logger.info("SCRAPE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total prompts:               {total_prompts}")
        logger.info(f"Skipped (pre-existing):      {skipped_count}")
        logger.info(f"Started:                     {started_count}")
        logger.info(f"Completed:                   {completed_count}")
        logger.info(f"Failed:                      {failed_count}")
        logger.info(f"Total listings extracted:    {total_listings}")
        logger.info(f"Success rate:                {success_rate:.1f}%")
        logger.info(f"Avg listings/completed:      {avg_listings:.1f}")
        logger.info(f"Elapsed time:                {timedelta(seconds=int(total_elapsed_sec))}")
        logger.info("=" * 60)

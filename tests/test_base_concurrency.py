#!/usr/bin/env python3
import asyncio
import time
import unittest

from task.base import BaseScraper
from task.models import Listing, Prompt


class DummyCheckpoint:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.succeeded: list[str] = []
        self.failed: list[str] = []
        self.saved: dict[str, int] = {}

    def filter_prompts(self, prompts: list[Prompt]) -> list[Prompt]:
        return prompts

    def mark_started(self, prompt: Prompt) -> None:
        self.started.append(prompt.query)

    def save_listings(self, prompt: Prompt, listings: list[Listing]) -> None:
        self.saved[prompt.query] = len(listings)

    def mark_succeeded(self, prompt: Prompt) -> None:
        self.succeeded.append(prompt.query)

    def mark_failed(self, prompt: Prompt, reason: str = "") -> None:
        self.failed.append(prompt.query)


class DummyScraper(BaseScraper):
    async def scrape(self, prompts: list[Prompt], limit: int) -> list[Listing]:
        await asyncio.sleep(0.05)
        prompt = prompts[0]
        return [
            Listing(
                name=f"listing-{prompt.query}",
                lat=0.0,
                lon=0.0,
                url=f"https://example.com/{prompt.query}",
                query=prompt.query,
            )
        ]


class BaseConcurrencyTests(unittest.TestCase):
    def test_checkpoint_mode_processes_prompts_concurrently(self) -> None:
        prompts = [Prompt(query=f"q-{i}") for i in range(6)]
        checkpoint = DummyCheckpoint()
        scraper = DummyScraper(max_concurrency=3)

        start = time.perf_counter()
        listings = scraper.run(prompts, limit=1, checkpoint=checkpoint, show_progress=False)
        elapsed = time.perf_counter() - start

        self.assertEqual(len(listings), len(prompts))
        self.assertEqual(len(checkpoint.started), len(prompts))
        self.assertEqual(len(checkpoint.succeeded), len(prompts))
        self.assertEqual(len(checkpoint.failed), 0)

        # Sequential would be ~0.30s for 6x0.05s; concurrency=3 should be materially lower.
        self.assertLess(elapsed, 0.22)


if __name__ == "__main__":
    unittest.main()

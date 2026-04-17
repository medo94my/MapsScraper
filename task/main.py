#!/usr/bin/env python3
from dataclasses import dataclass
import pathlib
from urllib.parse import quote
from typing import Iterable
import asyncio
# errors handlers


class MissingPromptFile(Exception):
    """Raised when the provided prompt file path does not exist."""


class WrongPromptFile(Exception):
    """Raised when the prompt file has no usable prompt lines."""


@dataclass
class Prompt:
    query: str


@dataclass
class Listing:
    name: str
    lat: float
    lon: float
    url: str
    address: str = ""
    website: str = ""
    rating: str = ""
    phone: str = ""


class MapsScraper:
    def __init__(self, headless=False):
        self.headless = headless

    async def _safe_text(self, locator) -> str:
        """Return trimmed text content or empty string when the locator has no match."""
        if await locator.count() == 0:
            return ""
        value = await locator.text_content()
        return (value or "").strip()

    async def _safe_attr(self, locator, attr: str, timeout: int | None = None) -> str:
        """Return an attribute value with a guarded timeout to avoid hard failures."""
        if await locator.count() == 0:
            return ""
        try:
            if timeout is None:
                value = await locator.get_attribute(attr)
            else:
                value = await locator.get_attribute(attr, timeout=timeout)
            return (value or "").strip()
        except Exception:
            return ""

    async def _prepare_results_feed(self, page):
        """Move focus to results feed when available so scrolling targets the card list."""
        feed_locator = page.locator('div[role="feed"]')
        has_feed = await feed_locator.count() > 0
        if has_feed:
            box = await feed_locator.bounding_box()
            if box:
                await page.mouse.move(box["x"], box["y"])
        else:
            print("Feed container not found")
        return feed_locator, has_feed

    async def _load_place_links(self, page, feed_locator, has_feed: bool, limit: int):
        """Load place links by repeatedly triggering lazy-loading until limit or stagnation."""
        await page.wait_for_selector('a[href*="/maps/place/"]', timeout=10000)
        links = page.locator('a[href*="/maps/place/"]')

        previous_count = 0
        stagnant_rounds = 0
        max_scroll_rounds = 40

        for _ in range(max_scroll_rounds):
            current_count = await links.count()
            if current_count >= limit or current_count == 0:
                break

            if current_count == previous_count:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                previous_count = current_count

            if stagnant_rounds >= 5:
                break

            await links.nth(current_count - 1).scroll_into_view_if_needed()
            if has_feed:
                await page.mouse.wheel(0, 800)
            else:
                await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(500)

        return links

    async def _collect_place_candidates(self, links, limit: int):
        """Collect stable href/name pairs from the loaded result cards."""
        candidates: list[tuple[str, str]] = []
        seen_hrefs: set[str] = set()
        link_count = min(await links.count(), limit)

        for index in range(link_count):
            link = links.nth(index)
            href = await link.get_attribute("href")
            if not href or "/maps/place/" not in href or href in seen_hrefs:
                continue

            card = link.locator('xpath=ancestor::div[@role="article"][1]')
            card_name = await self._safe_text(card.locator(".qBF1Pd").first)
            fallback_name = card_name if card_name else "Unknown"

            seen_hrefs.add(href)
            candidates.append((href, fallback_name))

        return candidates

    async def _extract_listing_from_href(self, detail_page, href: str, fallback_name: str):
        """Extract one Listing by opening the place URL in a dedicated details page."""
        if "/maps/place/" not in href:
            return None

        lat, lon = self.extract_coordinates(href)

        await detail_page.goto(href, wait_until="domcontentloaded", timeout=20000)

        details_panel = detail_page.locator('div[role="main"]:visible').filter(
            has=detail_page.locator("h1.DUwDvf")
        ).last
        title_locator = details_panel.locator("h1.DUwDvf").first
        await title_locator.wait_for(timeout=7000)

        panel_name = await self._safe_text(title_locator)
        name = fallback_name
        if panel_name and panel_name.lower() != "results":
            name = panel_name

        address = await self._safe_text(details_panel.locator('button[data-item-id="address"]').first)
        website = await self._safe_attr(
            details_panel.locator('a[data-item-id="authority"]').first,
            "href",
            timeout=3000,
        )
        phone_text = await self._safe_text(details_panel.locator('button[data-item-id="phone"]').first)
        rating = await self._safe_text(details_panel.locator('[aria-label*="stars"]').first)

        return Listing(
            name=name,
            address=address,
            website=website,
            phone=phone_text,
            rating=rating,
            lat=lat,
            lon=lon,
            url=href,
        )

    async def scrape(self, prompts: list[Prompt], limit: int) -> list[Listing]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is not installed. Please install it using 'pip install playwright' and run 'playwright install' to set up the browsers."
            )

        all_listings: list[Listing] = []
        global_seen_keys: set[str] = set()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)

            try:
                for prompt in prompts:
                    listings = self._srape_single_prompt(
                        browser, prompt, limit, global_seen_keys
                    )
                    all_listings.extend(await listings)
            except Exception as e:
                print(f"An error occurred while scraping: {e}")
            return all_listings

    def extract_coordinates(self, link_data):
        lat = (
            link_data.split("!3d")[1].split("!4d")[0]
            if "!3d" in link_data and "!4d" in link_data
            else None
        )
        lon = link_data.split("!4d")[1].split("!")[0] if "!4d" in link_data else None
        if lat and lon:
            return (float(lat), float(lon))
        return (0.0, 0.0)

    async def _srape_single_prompt(
        self, browser, prompt: Prompt, limit: int, global_seen_keys: set[str]
    ) -> list[Listing]:
        """Scrape a single prompt and return listings."""
        listings: list[Listing] = []
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()
        detail_page = await context.new_page()
        try:
            url = f"https://www.google.com/maps/search/{quote(prompt.query)}"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            feed_locator, has_feed = await self._prepare_results_feed(page)
            links = await self._load_place_links(page, feed_locator, has_feed, limit)
            candidates = await self._collect_place_candidates(links, limit)

            for href, fallback_name in candidates:
                listing = await self._extract_listing_from_href(detail_page, href, fallback_name)
                if listing is None:
                    continue

                listing_key = f"{listing.name}_{listing.lat}_{listing.lon}"
                if listing_key not in global_seen_keys:
                    global_seen_keys.add(listing_key)
                    listings.append(listing)
            print(listings)
            return listings
        except Exception as e:
            print(f"An error occurred while scraping prompt '{prompt.query}': {e}")
            return listings
        finally:
            await detail_page.close()
            await context.close()

    def read_prompt_file(self, file_path):
        prompt_path = pathlib.Path(file_path)

        if not prompt_path.exists() and prompt_path.name == "prompts.txt":
            candidate_prompts = prompt_path.parent / "inputs" / "prompts.txt"
            if candidate_prompts.exists():
                prompt_path = candidate_prompts

        if not prompt_path.exists():
            raise MissingPromptFile(f"Prompt file {file_path} is missing")

        raw_prompts = prompt_path.read_text().splitlines()
        prompts = [
            Prompt(query=raw_prompt)
            for raw_prompt in raw_prompts
            if raw_prompt.strip() != ""
        ]
        if len(prompts) == 0:
            raise WrongPromptFile(
                f"Prompt file {file_path} is empty or has invalid format"
            )
        return prompts

    def run(self, prompts: Iterable[Prompt], limit=10) -> Iterable[Listing]:
        prompts_list = list(prompts)
        all_listings: list[Listing] = []
        if len(prompts_list) == 0:
            return all_listings
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            all_listings = loop.run_until_complete(self.scrape(prompts_list, limit))
        except Exception as e:
            print(f"An error occurred during scraping: {e}")
        return all_listings

    def write_jsonl(self, listings: Iterable[Listing], output_path: str):
        import json

        with open(output_path, "w") as f:
            for listing in listings:
                json_line = json.dumps(listing.__dict__)
                f.write(json_line + "\n")

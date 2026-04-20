#!/usr/bin/env python3
"""Google Maps business listing scraper using Playwright."""

import re
from urllib.parse import quote

from playwright.async_api import async_playwright, Browser, Page

from task.base import BaseScraper
from task.logger import get_logger
from task.models import Listing, Prompt
from task.normalizers import ListingNormalizer
from task.retries import RetryConfig, retry_with_backoff


logger = get_logger("task.scraper")

# Timeout constants (in milliseconds)
TIMEOUT_FEED_MS = 5000  # Wait for results feed or place links
TIMEOUT_PLACE_LINK_MS = 10000  # Wait for first place link in feed
TIMEOUT_DETAIL_PANEL_MS = 7000  # Wait for detail panel title (h1.DUwDvf)
TIMEOUT_NAV_MS = 20000  # Wait for page navigation
TIMEOUT_SECONDARY_MS = 3000  # Wait for secondary detail fields (address, phone)

# Scroll configuration
MAX_SCROLL_ROUNDS = 40  # Max iterations scrolling feed
STAGNATION_THRESHOLD = 5  # Rounds without new results before stopping scroll
EXTRA_CANDIDATE_MULTIPLIER = 3  # Collect more hrefs to absorb extraction failures
MAX_CANDIDATE_ATTEMPTS = 120  # Hard cap for detail-page attempts per prompt


class MapsScraper(BaseScraper):
    """Google Maps scraper — implements :meth:`BaseScraper.scrape`.
    
    Features:
        - Two-stage extraction: URL collection → detail page navigation
        - Retry with exponential backoff on TimeoutError
        - Adaptive timeout learning (learns from actual page load times)
        - Cross-prompt deduplication with lock-protected set
        - Graceful partial failure recovery
    """

    _RATING_RE = re.compile(r"\b([0-5](?:[.,]\d)?)\b")
    _PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{6,}\d)")

    def __init__(
        self,
        headless: bool | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        """Initialize MapsScraper.
        
        Args:
            headless: Browser headless mode. If omitted, reads SCRAPER_HEADLESS
                (default: True).
            max_concurrency: Max concurrent prompts (default: 1). Higher values use
                multiple browser contexts with shared deduplication.
        """
        super().__init__(headless=headless, max_concurrency=max_concurrency)
        self.normalizer = ListingNormalizer()

    async def _get_results_layout_hint(self, page: Page) -> str:
        """Best-effort layout hint for diagnostics when feed is missing.
        
        Args:
            page: Playwright page object.
        
        Returns:
            String describing the detected layout ("place_links_present",
            "consent_screen", "unknown_layout", or "layout_probe_failed").
        """
        try:
            place_links = await page.locator('a[href*="/maps/place/"]').count()
            if place_links > 0:
                return "place_links_present"

            consent_form = await page.locator('form[action*="consent"]').count()
            consent_iframe = await page.locator('iframe[src*="consent"]').count()
            if consent_form > 0 or consent_iframe > 0:
                return "consent_screen"

            return "unknown_layout"
        except Exception:
            return "layout_probe_failed"

    async def _prepare_results_feed(self, page: Page):
        """Move focus to results feed when available so scrolling targets the card list.
        
        Args:
            page: Playwright page object.
        
        Returns:
            Tuple of (feed_locator, has_feed: bool).
        """
        # Maps can render results feed late; wait briefly for either feed or links.
        try:
            await page.wait_for_selector(
                'div[role="feed"], a[href*="/maps/place/"]',
                timeout=TIMEOUT_FEED_MS,
            )
        except Exception:
            pass

        feed_locator = page.locator('div[role="feed"]').first
        has_feed = await feed_locator.count() > 0
        if has_feed:
            box = await feed_locator.bounding_box()
            if box:
                await page.mouse.move(box["x"], box["y"])
        else:
            hint = await self._get_results_layout_hint(page)
            logger.info(
                "Results feed not present; using page-scroll fallback (layout=%s)",
                hint,
            )
        return feed_locator, has_feed

    async def _load_place_links(self, page: Page, has_feed: bool, limit: int):
        """Load place links by repeatedly triggering lazy-loading until limit or stagnation.
        
        Args:
            page: Playwright page object.
            has_feed: Whether results feed locator is visible.
            limit: Target number of place links to collect.
        
        Returns:
            Locator for place links (a[href*="/maps/place/"]).
        """
        await page.wait_for_selector('a[href*="/maps/place/"]', timeout=TIMEOUT_PLACE_LINK_MS)
        links = page.locator('a[href*="/maps/place/"]')
        target_links = min(MAX_CANDIDATE_ATTEMPTS, max(limit, limit * EXTRA_CANDIDATE_MULTIPLIER))

        previous_count = 0
        stagnant_rounds = 0

        for _ in range(MAX_SCROLL_ROUNDS):
            current_count = await links.count()
            if current_count >= target_links or current_count == 0:
                break

            if current_count == previous_count:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                previous_count = current_count

            if stagnant_rounds >= STAGNATION_THRESHOLD:
                break

            await links.nth(current_count - 1).scroll_into_view_if_needed()
            if has_feed:
                await page.mouse.wheel(0, 800)
            else:
                await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(500)

        return links

    async def _collect_place_candidates(self, links, limit: int):
        """Collect stable href/name pairs from the loaded result cards.
        
        Args:
            links: Locator for place links.
            limit: Maximum number of candidates to collect.
        
        Returns:
            List of (href, fallback_name) tuples.
        """
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

    async def _extract_rating_text(self, details_panel) -> str:
        """Extract rating with multilingual selector fallbacks."""
        rating = await self._safe_text(details_panel.locator('[aria-label*="stars"]').first)
        if rating:
            return rating

        alt_rating = details_panel.locator(
            '[aria-label*="star"], [aria-label*="stars"], '
            '[aria-label*="rating"], [aria-label*="نجمة"], [aria-label*="تقييم"]'
        ).first
        aria_label = await self._safe_attr(alt_rating, "aria-label", timeout=TIMEOUT_SECONDARY_MS)
        candidate_text = aria_label or await self._safe_text(alt_rating)
        if not candidate_text:
            return ""

        match = self._RATING_RE.search(candidate_text)
        return match.group(1).replace(",", ".") if match else ""

    async def _extract_phone_text(self, details_panel) -> str:
        """Extract phone with attribute and text fallbacks."""
        phone = await self._safe_text(
            details_panel.locator(
                'button[data-item-id="phone"], button[data-item-id*="phone"], '
                'button[aria-label*="Phone"], button[aria-label*="الهاتف"]'
            ).first
        )
        if phone:
            return phone

        tel_href = await self._safe_attr(
            details_panel.locator('a[href^="tel:"]').first,
            "href",
            timeout=TIMEOUT_SECONDARY_MS,
        )
        if tel_href.startswith("tel:"):
            return tel_href.removeprefix("tel:")

        panel_text = await self._safe_text(details_panel)
        match = self._PHONE_RE.search(panel_text)
        return match.group(1) if match else ""

    @retry_with_backoff(
        config=RetryConfig(max_attempts=3, base_delay=0.5, max_delay=5.0)
    )
    async def _extract_listing_from_href(
        self,
        detail_page: Page,
        href: str,
        fallback_name: str,
        query: str,
    ) -> Listing | None:
        """Extract one Listing by opening the place URL in a dedicated details page.
        
        This method is decorated with @retry_with_backoff to gracefully handle
        transient TimeoutErrors when waiting for detail page elements to load.
        
        Args:
            detail_page: Playwright page for detail view navigation.
            href: Google Maps place URL (e.g., maps.google.com/maps/place/...).
            fallback_name: Card-level name to use if detail panel name is unavailable.
            query: Original search prompt query for traceability.
        
        Returns:
            Normalized Listing object, or None if href is invalid or extraction fails.
        
        Raises:
            TimeoutError: If detail panel elements don't appear within timeout.
                Caught by @retry_with_backoff for up to 3 attempts.
        """
        if "/maps/place/" not in href:
            return None

        lat, lon = self.extract_coordinates(href)

        await detail_page.goto(href, wait_until="domcontentloaded", timeout=TIMEOUT_NAV_MS)

        details_panel = detail_page.locator('div[role="main"]:visible').filter(
            has=detail_page.locator("h1.DUwDvf")
        ).last
        title_locator = details_panel.locator("h1.DUwDvf").first
        await title_locator.wait_for(timeout=TIMEOUT_DETAIL_PANEL_MS)

        panel_name = await self._safe_text(title_locator)
        name = fallback_name
        if panel_name and panel_name.lower() != "results":
            name = panel_name

        address = await self._safe_text(details_panel.locator('button[data-item-id="address"]').first)
        website = await self._safe_attr(
            details_panel.locator('a[data-item-id="authority"]').first,
            "href",
            timeout=TIMEOUT_SECONDARY_MS,
        )
        phone_text = await self._extract_phone_text(details_panel)
        rating = await self._extract_rating_text(details_panel)

        return self.normalizer.normalize_listing(Listing(
            name=name,
            address=address,
            website=website,
            phone=phone_text,
            rating=rating,
            lat=lat,
            lon=lon,
            url=href,
            query=query,
        ))

    async def scrape(self, prompts: list[Prompt], limit: int) -> list[Listing]:
        """Scrape listings for multiple prompts sequentially with deduplication.
        
        Args:
            prompts: List of search prompts.
            limit: Target listings per prompt (may be fewer if feed exhausts).
        
        Returns:
            List of deduplicated Listing objects.
        """
        all_listings: list[Listing] = []
        global_seen_keys: set[str] = set()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                for prompt in prompts:
                    listings = await self._scrape_single_prompt(
                        browser, prompt, limit, global_seen_keys
                    )
                    all_listings.extend(listings)
            except Exception:
                logger.exception("An error occurred while scraping")
            return all_listings

    _COORD_RE = re.compile(r"!3d(-?[\d.]+)!4d(-?[\d.]+)")

    def extract_coordinates(self, link_data: str) -> tuple[float, float]:
        m = self._COORD_RE.search(link_data)
        if m:
            return (float(m.group(1)), float(m.group(2)))
        return (0.0, 0.0)

    async def _scrape_single_prompt(
        self,
        browser: Browser,
        prompt: Prompt,
        limit: int,
        global_seen_keys: set[str],
    ) -> list[Listing]:
        """Scrape a single prompt and return deduplicated listings.
        
        Opens a new browser context, navigates to the Maps search URL,
        collects result cards, extracts details from each card's detail page,
        and deduplicates using a global seen-key set.
        
        Args:
            browser: Playwright browser instance.
            prompt: Search prompt with query string.
            limit: Target number of listings to extract (may return fewer).
            global_seen_keys: Shared set of dedupe keys across all prompts.
        
        Returns:
            List of normalized Listing objects, deduplicated globally.
            May return fewer than limit if feed exhausts or extraction fails.
        """
        listings: list[Listing] = []
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        detail_page = await context.new_page()
        try:
            url = f"https://www.google.com/maps/search/{quote(prompt.query)}"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            _, has_feed = await self._prepare_results_feed(page)
            links = await self._load_place_links(page, has_feed, limit)
            candidate_limit = min(
                MAX_CANDIDATE_ATTEMPTS,
                max(limit, limit * EXTRA_CANDIDATE_MULTIPLIER),
            )
            candidates = await self._collect_place_candidates(links, candidate_limit)

            for href, fallback_name in candidates:
                if len(listings) >= limit:
                    break
                listing = await self._extract_listing_from_href(
                    detail_page,
                    href,
                    fallback_name,
                    prompt.query,
                )
                if listing is None:
                    continue

                listing_key = self.normalizer.dedupe_key(listing)
                if listing_key in global_seen_keys:
                    continue
                global_seen_keys.add(listing_key)
                listings.append(listing)
            logger.info("Collected %s listings for prompt '%s'", len(listings), prompt.query)
            return listings
        except Exception:
            logger.exception("An error occurred while scraping prompt '%s'", prompt.query)
            return listings
        finally:
            await detail_page.close()
            await context.close()

"""Mzad Qatar auction scraper.

Scrapes active lots from a Mzad Yard session page, then enriches each lot by
visiting its detail page.

Usage (programmatic):
    from mzad_qatar import MzadScraper

    scraper = MzadScraper()
    lots = scraper.run(
        "https://mzadqatar.com/en/bidding/mzad-yard-3820",
        max_lots=50,
    )
    for lot in lots:
        print(lot.to_dict())
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Optional

from task.logger import get_logger
from mzad_qatar.models import MzadLot

logger = get_logger("mzad_qatar.scraper")

_BASE_URL = "https://mzadqatar.com"


# ---------------------------------------------------------------------------
# Text-extraction helpers
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> float:
    """Extract the first numeric value (with optional commas) from *text*."""
    m = re.search(r"[\d,]+", text.replace("\xa0", ""))
    if not m:
        return 0.0
    return float(m.group(0).replace(",", ""))


def _parse_int(text: str) -> int:
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else 0


def _extract_label_value(text: str, label: str) -> str:
    """Return the value that appears right after *label* in a block of inner-text.

    The detail page renders spec rows as:
        <label>\\n\\n<value>
    so we look for label followed by one or more newlines then capture one line.
    """
    pattern = rf"{re.escape(label)}\n+([^\n]+)"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extract_price_near_label(text: str, label: str) -> float:
    """Extract QAR price from text near *label*.

    Looks for the pattern:  <label> ... <number> QAR
    within a 200-character window, so it is not fooled by countdown timers or
    other numeric values that happen to follow the label on the page.
    """
    pattern = rf"{re.escape(label)}(.{{0,200}}?)([\d,]+)\s*QAR"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not m:
        return 0.0
    return float(m.group(2).replace(",", ""))


def _extract_inline(text: str, label: str) -> str:
    """Return value for patterns like  'Minor Accidents: 1'."""
    pattern = rf"{re.escape(label)}\s*:\s*([^\n]+)"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# MzadScraper
# ---------------------------------------------------------------------------

class MzadScraper:
    """Playwright-based scraper for Mzad Qatar Yard auction sessions."""

    def __init__(self, headless: Optional[bool] = None) -> None:
        if headless is None:
            val = os.getenv("SCRAPER_HEADLESS", "").strip().lower()
            headless = val in {"1", "true", "yes", "on"}
        self.headless = headless

    # ------------------------------------------------------------------
    # Public sync entry-point
    # ------------------------------------------------------------------

    def run(
        self,
        session_url: str,
        max_lots: int = 100,
        output_path: Optional[str] = None,
    ) -> list[MzadLot]:
        """Scrape *session_url* and return up to *max_lots* active MzadLot records.

        If *output_path* is given the results are written as JSONL to that file.
        """
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            lots = loop.run_until_complete(self._scrape(session_url, max_lots))
        except Exception:
            logger.exception("Fatal error during Mzad scrape")
            lots = []
        finally:
            if loop is not None:
                loop.close()

        if output_path:
            self.write_jsonl(lots, output_path)

        return lots

    @staticmethod
    def write_jsonl(lots: list[MzadLot], path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            for lot in lots:
                fh.write(json.dumps(lot.to_dict(), ensure_ascii=False) + "\n")
        logger.info("Wrote %d lots to %s", len(lots), path)

    # ------------------------------------------------------------------
    # Async implementation
    # ------------------------------------------------------------------

    async def _scrape(self, session_url: str, max_lots: int) -> list[MzadLot]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ImportError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            ) from exc

        lots: list[MzadLot] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                # Patch navigator.webdriver so Cloudflare doesn't see the automation flag
                await context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                listing_page = await context.new_page()
                # Reuse listing_page for detail navigation to keep CF clearance + Referer
                detail_page = listing_page

                # --- collect lot URLs across all session pages ---
                lot_urls = await self._collect_lot_urls(listing_page, session_url, max_lots)
                logger.info("Found %d active lot(s) to process", len(lot_urls))

                # --- visit each lot detail page ---
                for idx, (lot_url, card_meta) in enumerate(lot_urls):
                    logger.info("[%d/%d] Scraping %s", idx + 1, len(lot_urls), lot_url)
                    lot = await self._extract_lot_detail(detail_page, lot_url, card_meta, session_url)
                    if lot:
                        lots.append(lot)

            except Exception:
                logger.exception("Error during Mzad scrape")
            finally:
                await browser.close()

        logger.info("Done — collected %d lot(s)", len(lots))
        return lots

    # ------------------------------------------------------------------
    # Step 1: collect lot URLs (with multi-page support)
    # ------------------------------------------------------------------

    async def _collect_lot_urls(
        self, page, base_session_url: str, max_lots: int
    ) -> list[tuple[str, dict]]:
        """Return (absolute_url, card_metadata) pairs for all active lots."""
        # Normalise — strip any existing currentActivePage param
        session_root = re.sub(r"[?&]currentActivePage=\d+", "", base_session_url).rstrip("?&")

        all_pairs: list[tuple[str, dict]] = []
        page_num = 1

        while len(all_pairs) < max_lots:
            url = f"{session_root}?currentActivePage={page_num}"
            logger.info("Loading session page %d: %s", page_num, url)
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            # Wait for the lot list to appear
            try:
                await page.wait_for_selector('a[href*="/lots/"]', timeout=10000)
            except Exception:
                logger.info("No lot links found on page %d — stopping pagination", page_num)
                break

            pairs = await self._extract_active_lot_links(page)
            if not pairs:
                logger.info("No active lots on page %d — stopping pagination", page_num)
                break

            all_pairs.extend(pairs)
            logger.info("Page %d: found %d active lot(s) (total so far: %d)", page_num, len(pairs), len(all_pairs))

            # Check if there is a next-page button/link
            has_next = await self._has_next_page(page, page_num)
            if not has_next:
                break
            page_num += 1

        return all_pairs[:max_lots]

    async def _extract_active_lot_links(self, page) -> list[tuple[str, dict]]:
        """Extract (url, metadata) only from the 'Active lots' section."""
        result: list[dict] = await page.evaluate(r"""
            () => {
                // Find a heading that contains "Active lots" (case-insensitive)
                const headings = Array.from(document.querySelectorAll('h5, h4, h3, h2'));
                let container = null;
                for (const h of headings) {
                    if (/active\s+lots/i.test(h.textContent)) {
                        // The container holding lot cards is the next sibling element
                        container = h.nextElementSibling || h.parentElement.nextElementSibling;
                        break;
                    }
                }
                if (!container) return [];

                const links = Array.from(container.querySelectorAll('a[href*="/lots/"]'));
                return links.map(a => ({
                    href: a.href,
                    text: a.innerText.trim(),
                }));
            }
        """)

        pairs: list[tuple[str, dict]] = []
        for item in result:
            href = item.get("href", "")
            if not href:
                continue
            meta = self._parse_card_text(item.get("text", ""))
            pairs.append((href, meta))
        return pairs

    async def _has_next_page(self, page, current_page: int) -> bool:
        """Check if a 'next page' link or button exists."""
        next_page = current_page + 1
        exists: bool = await page.evaluate(
            f"""
            () => {{
                const all = Array.from(document.querySelectorAll('a, button'));
                return all.some(el => {{
                    const href = el.href || '';
                    const txt = el.textContent.trim();
                    return href.includes('currentActivePage={next_page}') || txt === '{next_page}';
                }});
            }}
            """
        )
        return exists

    def _parse_card_text(self, text: str) -> dict:
        """Parse the compact card link text into structured metadata.

        Card text format (observed):
            "Hyundai Accent Model 2025, Y-14571 17h 58m 15s 0 21,500 QAR"
        """
        meta: dict = {"raw_card_text": text}

        # Time remaining — e.g. "17h 58m 15s"
        time_m = re.search(r"(\d+h\s*\d+m\s*\d+s)", text)
        meta["time_remaining"] = time_m.group(1).strip() if time_m else ""

        # Price — last "N,NNN QAR" pattern
        price_m = re.findall(r"([\d,]+)\s*QAR", text)
        meta["current_price"] = float(price_m[-1].replace(",", "")) if price_m else 0.0

        # Bid count — number just before QAR price (after the countdown)
        after_time = re.sub(r"\d+h\s*\d+m\s*\d+s", "", text)
        nums = re.findall(r"[\d,]+", after_time)
        if len(nums) >= 2:
            try:
                meta["bid_count"] = int(nums[0].replace(",", ""))
            except ValueError:
                meta["bid_count"] = 0
        else:
            meta["bid_count"] = 0

        return meta

    # ------------------------------------------------------------------
    # Step 2: extract detail from lot page
    # ------------------------------------------------------------------

    async def _extract_lot_detail(
        self,
        page,
        lot_url: str,
        card_meta: dict,
        auction_url: str,
    ) -> Optional[MzadLot]:
        try:
            await page.goto(lot_url, wait_until="networkidle", timeout=30000)
        except Exception:
            # networkidle can time-out on slow pages; try domcontentloaded fallback
            try:
                await page.goto(lot_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)
            except Exception:
                logger.warning("Failed to load lot page: %s", lot_url)
                return None

        try:
            # Use JS evaluation to get body text — avoids locator-timeout issues
            # that occur when headless Chrome is detected by anti-bot scripts.
            text: str = await page.evaluate("document.body.innerText")
            if not text or len(text.strip()) < 50:
                text = await page.evaluate("document.documentElement.innerText")
        except Exception:
            logger.warning("Could not read body text from %s", lot_url)
            return None

        lot = MzadLot(lot_url=lot_url, auction_url=auction_url)

        # --- lot id ---
        lot_id_m = re.search(r"Lot\s*#\s*(\d+)", text, re.IGNORECASE)
        lot.lot_id = lot_id_m.group(1) if lot_id_m else ""

        # --- title: derive from URL slug (most reliable, unaffected by live bid UI) ---
        # Slug format: "toyota-gxr-model-2024,-y-14586-39975" → "Toyota GXR Model 2024, Y-14586"
        slug = lot_url.rstrip("/").split("/lots/")[-1] if "/lots/" in lot_url else ""
        slug_no_id = re.sub(r"-\d+$", "", slug)          # remove trailing -<lot_id>
        slug_clean = slug_no_id.replace("-", " ").strip()
        title = slug_clean.title() if slug_clean else ""
        # Restore comma before plate: "2024  Y" → "2024, Y"
        title = re.sub(r"(\d{4})\s+(Y)", r"\1, \2", title, flags=re.IGNORECASE)
        # Restore hyphen in plate number: "Y 14586" → "Y-14586"
        title = re.sub(r"\bY (\d+)\b", r"Y-\1", title)
        lot.title = title

        # --- pricing ---
        # Label changes depending on bid state:
        #   0 bids  → "Starting price"
        #   1+ bids → "Current price"
        lot.starting_price = (
            _extract_price_near_label(text, "Starting price")
            or _extract_price_near_label(text, "Current price")
        )
        lot.min_increment = _parse_price(_extract_label_value(text, "Minimum increment"))

        # Live bid count and time from detail page (more reliable than card)
        tr_m = re.search(r"Time remaining:\s*([^\n]+)", text, re.IGNORECASE)
        lot.time_remaining = tr_m.group(1).strip() if tr_m else card_meta.get("time_remaining", "")

        nb_m = re.search(r"Number of bids:\s*(\d+)", text, re.IGNORECASE)
        lot.bid_count = int(nb_m.group(1)) if nb_m else card_meta.get("bid_count", 0)

        # current price = starting price when 0 bids, else parse live price widget
        lot.current_price = card_meta.get("current_price", lot.starting_price) or lot.starting_price

        # --- description block ---
        chassis_m = re.search(r"Chassis Number:\s*([^\n]+)", text, re.IGNORECASE)
        lot.chassis_number = chassis_m.group(1).strip() if chassis_m else ""

        lot.minor_accidents = _parse_int(_extract_inline(text, "Minor Accidents"))
        lot.major_accidents = _parse_int(_extract_inline(text, "Major Accidents"))
        lot.import_status = _extract_inline(text, "Import Status")

        # --- spec table (label on line N, value on line N+1) ---
        lot.make = _extract_label_value(text, "Motor type")
        lot.model = _extract_label_value(text, "Class")
        year_str = _extract_label_value(text, "Manufacture Year")
        lot.year = _parse_int(year_str)
        km_str = _extract_label_value(text, "Km")
        lot.mileage_km = _parse_int(km_str)
        lot.car_type = _extract_label_value(text, "Car Type")
        lot.gear_type = _extract_label_value(text, "Gear Type")
        lot.fuel_type = _extract_label_value(text, "Fuel Type")
        lot.condition = _extract_label_value(text, "Condition")
        lot.guarantee = _extract_label_value(text, "Guarantee")
        lot.city = _extract_label_value(text, "City")

        # Color appears both in description and spec table; prefer spec table
        color_spec = _extract_label_value(text, "Color")
        lot.color = color_spec or _extract_inline(text, "Color")

        # Cylinders
        cyl_str = _extract_label_value(text, "Number of Cylinders")
        lot.cylinders = _parse_int(cyl_str)

        # --- plate number: extract from URL slug directly (reliable even if title truncated) ---
        plate_m = re.search(r"[Yy]-(\d+)", slug_no_id)
        lot.plate_number = f"Y-{plate_m.group(1)}" if plate_m else ""

        logger.info(
            "Extracted lot #%s: %s | start=%s current=%s QAR | make=%s model=%s year=%s bids=%d",
            lot.lot_id, lot.title, lot.starting_price, lot.current_price,
            lot.make, lot.model, lot.year, lot.bid_count,
        )
        return lot

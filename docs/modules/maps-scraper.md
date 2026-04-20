# MapsScraper reference

This page documents the Google Maps-specific scraper implementation.

## Module purpose

task/scraper.py implements concrete extraction logic while inheriting runtime and
I/O behavior from BaseScraper.

## Class: MapsScraper(BaseScraper)

MapsScraper extracts Google Maps listing details using a two-stage approach:
result link collection, then dedicated detail-page extraction per candidate.

### __init__(headless: bool = True, max_concurrency: int | None = None)

This constructor initializes base runtime settings and ListingNormalizer.

### _get_results_layout_hint(page: Page) -> str

This helper returns diagnostic hints when results feed is not detected.

Possible values:
- place_links_present
- consent_screen
- unknown_layout
- layout_probe_failed

### _prepare_results_feed(page: Page)

This helper waits for feed or place links and returns feed locator plus
availability flag.

Behavior:
- focuses feed area when present.
- logs fallback mode when feed is unavailable.

### _load_place_links(page: Page, has_feed: bool, limit: int)

This helper triggers lazy loading by scrolling until enough links or stagnation.

Stopping conditions:
- collected link count reaches limit.
- no links are found.
- count does not grow for stagnation threshold rounds.

### _collect_place_candidates(links, limit: int)

This helper builds unique candidate tuples of href and fallback name.

Behavior:
- skips duplicate or invalid href values.
- derives fallback name from card title.

### _extract_listing_from_href(detail_page, href, fallback_name, query)

This method extracts one listing from a place detail page.

Decorator behavior:
- wrapped with retry_with_backoff for timeout resilience.

Extraction behavior:
- validates href path.
- parses coordinates from URL.
- opens detail page and waits for title.
- extracts name, address, website, phone, and rating.
- normalizes listing before return.

Return behavior:
- returns None for invalid place href.

### scrape(prompts: list[Prompt], limit: int) -> list[Listing]

This async method is the required BaseScraper implementation.

Behavior:
- launches one Chromium browser.
- processes prompts sequentially in this method.
- keeps global dedupe key set across prompts.
- returns aggregated deduplicated listings.

Note:
- parallel prompt orchestration in checkpoint mode happens in BaseScraper,
  which calls scrape with one prompt per worker.

### extract_coordinates(link_data: str) -> tuple[float, float]

This helper extracts latitude and longitude from Google URL tokens.

Behavior:
- matches !3d<lat>!4d<lon> pattern.
- returns 0.0, 0.0 when pattern is missing.

### _scrape_single_prompt(browser, prompt, limit, global_seen_keys)

This helper runs one prompt end to end.

Behavior:
- opens isolated browser context.
- opens search and detail pages.
- loads candidates and extracts details.
- deduplicates against global key set.
- closes pages and context in finally block.

Failure behavior:
- logs prompt-level exceptions and returns partially collected results.

## Constants and tuning points

This module defines timeout and scroll constants for extraction behavior.

Examples:
- TIMEOUT_FEED_MS
- TIMEOUT_PLACE_LINK_MS
- TIMEOUT_DETAIL_PANEL_MS
- MAX_SCROLL_ROUNDS
- STAGNATION_THRESHOLD

Tune these cautiously and validate against both extraction quality and runtime.

## Next steps

When selectors break due to Maps UI changes, update this module first, then run
full tests plus driver verification.

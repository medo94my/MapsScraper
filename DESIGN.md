# Design Notes

## 1. Extraction Strategy

**Approach: Playwright browser automation with a two-stage URL-collect → detail-navigate pattern.**

Google Maps renders entirely in JavaScript — there is no stable static HTML or public JSON endpoint that mirrors search results. Approaches considered:

| Approach | Why rejected |
|---|---|
| Direct HTTP requests to Maps API | Violates the constraint banning Google APIs |
| Intercepting XHR/Fetch network requests | Map tile and feature responses are protobuf-encoded and unstable across deploys |
| Direct card-click navigation | Frequently produces stale React state — the detail panel sometimes shows the previous result |
| Selenium | Heavier resource profile, slower browser setup; Playwright's async API fits async Python better |

The chosen approach:

1. **Scroll phase** — Navigate to the search URL and scroll the `div[role="feed"]` until `limit` unique place links are collected or five stagnant scroll rounds pass.
2. **Detail phase** — Open each collected `href` in a dedicated detail page and extract fields from `div[role="main"]:visible h1.DUwDvf` and associated data-item-id buttons.

Separating the two phases eliminates the stale-UI problem: detail pages are loaded from a stable canonical URL rather than from a UI state that depends on the previous navigation.

## 2. Brittle Points and Likely Failure Modes

| Point | Risk | Current mitigation |
|---|---|---|
| `div[role="feed"]` CSS selector | Google can change the role without notice | 5 s wait + fallback to `a[href*="/maps/place/"]` links even without the feed |
| `h1.DUwDvf` for place name | Class name is opaque and likely to be re-hashed | Fallback to card-level `.qBF1Pd` text collected during scroll phase |
| `button[data-item-id="address"]` | `data-item-id` is more stable than class names but still not a public contract | No fallback — field is optional and returns empty string |
| Coordinate extraction from URL | Relies on `@lat,lon,` pattern in Maps URLs | Regex covers the canonical format; returns `(0.0, 0.0)` on no-match |
| Scroll stagnation | Fewer than 30 results exist, or lazy-loading stops before limit | Stagnation guard exits after 5 rounds; count is logged |
| Consent / cookie gate | Redirects to a consent page in EU locales | Detected via layout hint; no automated bypass — documented and gracefully empty |
| Rate limiting or soft blocks | IP-level throttling after many requests | No current mitigation beyond natural timing from Playwright's render pauses |
| Language of results | Maps infers language from IP; Arabic queries return Arabic labels | Fields are stored as-is; `ListingNormalizer` applies NFC and mixed-script spacing |

## 3. Process, Tradeoffs, Shortcuts, and Dead Ends

**Process**

Development followed a module-boundary-first approach: data model (`models.py`), error types (`error.py`), base class (`base.py`), then the Maps-specific scraper (`scraper.py`). The normalizer layer was added after the first extraction runs produced messy phone and URL strings.

**Tradeoffs**

- *Headless vs. headed* — Headless is the default for unattended runs. You can
        set `SCRAPER_HEADLESS=0` to run headed mode for interactive selector
        debugging.
- *Speed vs. reliability* — The two-stage approach roughly doubles wall time compared to direct card clicking, but reduces failed extractions on dynamic pages significantly.
- *Concurrency* — Default concurrency is 1 (single browser, sequential prompts). Higher concurrency (`SCRAPER_MAX_CONCURRENCY`) opens one Playwright context per worker; the checkpoint and deduplication sets are protected by `asyncio.Lock`.
- *Checkpoint defaults* — `BaseScraper.run()` enables checkpoint persistence by default when `SCRAPER_CHECKPOINT_ENABLED=1`, even if no explicit `Checkpoint` object is passed.
- *Rating format* — Stored as the raw locator text (e.g. `"4.3 stars"`). Parsing to float was considered but deferred; the raw form is unambiguous and easy to post-process.

**Dead ends**

- Intercepting Maps protobuf responses — the binary encoding changes too frequently.
- Parsing canonical `application/ld+json` — Maps pages do not include structured data markup in a stable form.
- Using `page.evaluate()` to read React component state — internal state object paths are minified and change with every deploy.

## 4. Reliability: Retries, Timeouts, Checkpointing, Deduplication, Logging, Partial Failure Recovery

**Retries**

`_extract_listing_from_href` is decorated with `@retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.5, max_delay=5.0))`. On `PlaywrightTimeoutError` or `PlaywrightError` the method sleeps with exponential back-off and jitter before retrying. After three failures the listing is skipped and the prompt continues.

**Timeouts**

Each stage uses conservative but bounded waits:
- Feed or place-link availability: 5 s
- First place link presence: 10 s
- Detail panel (`h1.DUwDvf`): 7 s
- Secondary field locators: 3 s
- Page navigation: 20 s

All waits use `wait_for_selector` or `wait_for`, so they do not burn wall time when the element arrives early.

**Checkpointing**

`Checkpoint` writes two files:

- `output.jsonl` — one record per listing, flushed after each prompt completes.
- `output.jsonl.status.jsonl` — prompt lifecycle journal (`started` / `succeeded` / `failed`).

In explicit checkpoint mode (caller passes `Checkpoint`), `filter_prompts`
skips prompts with terminal `succeeded` status.

In implicit default mode (no explicit checkpoint passed), listings are still
persisted, but prompts are not pre-filtered. This keeps fixed-driver smoke
checks deterministic across repeated runs.

Failed prompts are retried automatically in subsequent explicit resume runs.

Environment controls:

- `SCRAPER_SHOW_PROGRESS` (default `1`)
- `SCRAPER_CHECKPOINT_ENABLED` (default `1`)
- `SCRAPER_CHECKPOINT_PATH` (default `output.jsonl`)

**Deduplication**

Global deduplication key: `normalized_name | lat | lon | website_host`

- `lat`/`lon` are rounded to 5 decimal places (~1 m precision) to absorb coordinate jitter.
- Name is normalized to NFC and case-folded before comparison.
- Cross-prompt deduplication is maintained via a shared `global_seen_keys` set protected by `asyncio.Lock`.

**Logging**

All log output uses the `task.logger` factory (`logging.getLogger`). Each module uses its own named logger (`task.scraper`, `task.checkpoint`, etc.), so log routing and level filtering can be configured per-module at runtime without touching source code.

**Partial failure recovery**

If a single detail-page extraction raises, the exception is caught, logged, and the listing is skipped. The prompt-level exception handler catches broader failures and writes a `failed` event to the status journal, leaving the prompt retryable on the next run.

## 5. Data Quality: Validation, Drift Detection, Completeness, Confidence

**Validation**

- `Listing.lat` and `Listing.lon` are floats extracted from the canonical Maps URL. A coordinate of `(0.0, 0.0)` indicates extraction failure and should be treated as missing.
- Phone numbers are normalized to `+E.164` prefix form when they start with `+` or `00`; otherwise digits only. Invalid strings return `""`.
- URLs are cleaned of UTM and tracking parameters and have `www.` stripped from the host for consistent deduplication.

**Completeness**

Only `name`, `lat`, `lon`, and `url` are required for a listing to be emitted. All other fields (`address`, `website`, `phone`, `rating`) are optional and default to `""`. Downstream consumers should treat `""` as absent.

**Drift detection**

Currently absent — there is no selector-health monitoring. In production, adding an assertion pass after each scrape run that checks the fraction of listings with missing fields per prompt would surface selector rot quickly. A rate of, e.g., >50% empty `address` fields across prompts that previously produced addresses is a strong signal of a layout change.

**Confidence**

No confidence score is attached to individual fields. A practical addition would be a boolean `is_coordinate_extracted: bool` and a `fields_found: list[str]` on each record to let consumers filter by reliability.

## 6. Adapting to a More Adversarial Target (e.g., Social Media)

Social media platforms (Instagram, LinkedIn, X/Twitter) apply layered bot-detection that goes well beyond Maps:

| Technique | Typical countermeasure |
|---|---|
| Browser fingerprinting | Use a real browser profile with realistic `navigator` properties; rotate user agents |
| Mouse / keyboard entropy analysis | Inject human-like timing jitter on mouse moves and keystrokes |
| TLS fingerprinting | Use a browser whose TLS stack matches the browser version (Playwright satisfies this) |
| Cookie / session freshness | Rotate authenticated sessions; cold sessions trigger challenges faster |
| IP reputation | Route traffic through residential proxies; avoid datacenter IP ranges |
| Rate limits | Add randomized inter-request delays; use exponential back-off with jitter on 429 responses |
| Login walls | Maintain a pool of authenticated accounts; detect and gracefully handle session expiry |
| CAPTCHA | Use a third-party CAPTCHA-solving service for persistent cases; flag and queue for human review |
| Shadow banning | Validate extracted result counts against baseline; alert when they drop unexpectedly |

The code structure already supports these adaptations: the `BaseScraper` interface isolates site-specific logic, so a new `SocialScraper(BaseScraper)` can plug in proxy rotation and session management without touching the checkpoint or normalization layers.

## 7. Scaling and Orchestration Across Many Prompts or Regions

**Current scale**

Single process, single Playwright browser, bounded concurrency via `SCRAPER_MAX_CONCURRENCY`.

**Scaling sketch**

```
┌─────────────────────────────────────────────────────────┐
│  Prompt queue (e.g., Redis or SQS)                      │
│  - populated by region × keyword product                 │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────▼────────┐
        │   Coordinator   │  (stateless, reads queue, distributes work)
        └────────┬────────┘
                 │ fan-out
        ┌────────▼────────────────────────────────────────┐
        │   Worker pool (N containers)                     │
        │   Each: Playwright + MapsScraper                 │
        │   Checkpoint writes to shared object store (S3)  │
        └────────┬────────────────────────────────────────┘
                 │ emit
        ┌────────▼────────┐
        │  Output store   │  (S3 / BigQuery / Postgres)
        └─────────────────┘
```

Key considerations:

- **Deduplication** — Move from in-process set to a shared key-value store (Redis `SADD`/`SISMEMBER`) so workers across containers share seen keys.
- **Checkpointing** — Replace file-based checkpoints with a database table keyed by `(run_id, prompt_query)` so any worker can resume a failed prompt.
- **Region targeting** — Pass a `gl` (country) and `hl` (language) parameter in the Maps URL to force results for a specific locale without relying on IP geolocation. Combine with a proxy pool that exits in the target country.
- **Rate control** — Implement a token-bucket rate limiter in the coordinator to cap requests per IP/minute; measure 429 rates per worker and auto-scale down if blocking increases.
- **Observability** — Emit structured metrics (listings_per_prompt,
  extraction_time, missing_field_rate) to a time-series store
  (Prometheus/CloudWatch) and alert on regression.

## 8. What I Would Improve With More Time

1. **Coordinate validation** — Listings with `lat == 0.0 and lon == 0.0` should be quarantined to a `suspect_output.jsonl` rather than mixed into the main output.

2. **Rating normalization** — Parse rating strings to `float` (e.g. `"4.3 stars"` → `4.3`) and expose `review_count` as a separate integer field.

3. **Opening hours extraction** — The detail panel exposes opening hours; extracting structured `{day: [open, close]}` maps would materially improve downstream usefulness.

4. **Category / business type** — The detail panel includes a category label (e.g. "Pharmacy", "Bookstore") that can anchor the result to the search intent and help downstream filtering.

5. **Selector health monitor** — A lightweight post-run check that flags when the fraction of populated fields drops below a rolling baseline per field, surfacing selector drift quickly.

6. **Proxy integration** — Parameterize the Playwright launch with a proxy URL so the scraper can be pointed at a residential proxy pool for higher-volume or adversarial use cases.

7. **Docker Compose with a pre-cached browser** — The current Dockerfile installs Playwright and downloads the Chromium binary at build time, which is correct; a Compose file would make multi-service setup (e.g., scraper + Redis for distributed deduplication) one command.

8. **Selector regression tests** — Fixture-based tests currently cover normalization. Adding a small set of recorded HTML snippets and asserting correct field extraction from them would catch CSS selector changes before they hit production.

---

## Notes on `task_driver.py` and the Exercise Contract

*Note: the driver contract is fixed for the take-home; these are suggestions for a future iteration.*

- **`test_run` searches live Maps** — this makes the test suite network-dependent and non-deterministic. An injected `scrape()` stub or a recorded-cassette approach (e.g., Playwright's HAR replay) would make the driver runnable in CI without a network connection.
- **No timeout on `test_run`** — a stuck browser would hang the driver indefinitely. A `asyncio.wait_for` or `subprocess.run(timeout=…)` wrapper would surface hangs cleanly.
- **`sys.exit(-1)` on failure** — exiting with a negative code works on most POSIX systems, but `-1` maps to exit code `255` on Linux. Using `sys.exit(1)` is more portable and conventional.
- **Single-file driver** — separating the test harness from the entry point (e.g., `tests/test_driver.py` vs. `run.py`) would let pytest collect and report driver-level failures alongside unit tests.

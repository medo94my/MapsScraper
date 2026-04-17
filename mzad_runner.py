#!/usr/bin/env python3
"""Standalone runner for the Mzad Qatar auction scraper.

Usage:
    python mzad_runner.py [SESSION_URL] [--max LOTS] [--out OUTPUT.jsonl] [--headed]

Examples:
    # Scrape default session, save to mzad_output.jsonl
    python mzad_runner.py

    # Custom session URL + limit
    python mzad_runner.py "https://mzadqatar.com/en/bidding/mzad-yard-3820" --max 30

    # Run with visible browser (useful for debugging)
    python mzad_runner.py --headed
"""
import argparse
import json
import sys

# Allow running from the repo root without installing the package
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from mzad_qatar.scraper import MzadScraper  # noqa: E402  (after sys.path fix)


DEFAULT_SESSION_URL = "https://mzadqatar.com/en/bidding/mzad-yard-3820"
DEFAULT_OUTPUT = "mzad_output.jsonl"
DEFAULT_MAX_LOTS = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mzad Qatar auction scraper")
    parser.add_argument(
        "session_url",
        nargs="?",
        default=DEFAULT_SESSION_URL,
        help=f"Session URL to scrape (default: {DEFAULT_SESSION_URL})",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=DEFAULT_MAX_LOTS,
        dest="max_lots",
        help=f"Maximum number of active lots to scrape (default: {DEFAULT_MAX_LOTS})",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUTPUT,
        dest="output",
        help=f"Output JSONL file path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (no visible window). Headed is the default because the site uses Cloudflare.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    headless = args.headless
    print(f"Session URL : {args.session_url}")
    print(f"Max lots    : {args.max_lots}")
    print(f"Output      : {args.output}")
    print(f"Headless    : {headless}")
    print()

    scraper = MzadScraper(headless=headless)
    lots = scraper.run(
        session_url=args.session_url,
        max_lots=args.max_lots,
        output_path=args.output,
    )

    if not lots:
        print("No lots were scraped. Check logs for details.")
        return 1

    print(f"\nScraped {len(lots)} active lot(s).\n")

    # Print a quick summary table
    header = f"{'#':<6} {'Make':<14} {'Model':<14} {'Year':<6} {'Bids':<6} {'Current Price (QAR)':<22} {'Title'}"
    print(header)
    print("-" * len(header))
    for i, lot in enumerate(lots, 1):
        print(
            f"{i:<6} {lot.make:<14} {lot.model:<14} {lot.year:<6} "
            f"{lot.bid_count:<6} {lot.current_price:<22,.0f} {lot.title}"
        )

    print(f"\nFull data written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

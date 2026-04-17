"""mzad_qatar — Mzad Qatar auction scraper package.

Public API:
    from mzad_qatar import MzadScraper, MzadLot
"""
from mzad_qatar.models import MzadLot
from mzad_qatar.scraper import MzadScraper

__all__ = ["MzadLot", "MzadScraper"]

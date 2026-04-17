"""Data models for the Mzad Qatar auction scraper."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MzadLot:
    """One active auction lot scraped from a Mzad Yard session page."""

    # --- identity ---
    lot_id: str = ""
    title: str = ""
    lot_url: str = ""
    auction_url: str = ""  # parent session page that linked to this lot

    # --- car attributes ---
    make: str = ""            # e.g. "Hyundai"
    model: str = ""           # e.g. "Accent"
    year: int = 0             # e.g. 2025
    plate_number: str = ""    # e.g. "Y-14571"
    chassis_number: str = ""
    color: str = ""
    car_type: str = ""        # Saloon / SUV / Pickup …
    gear_type: str = ""       # Automatic / Manual
    cylinders: int = 0
    fuel_type: str = ""
    condition: str = ""       # e.g. "Used- Good"
    guarantee: str = ""
    city: str = ""
    import_status: str = ""
    mileage_km: int = 0        # odometer reading when listed (0 if not disclosed)

    # --- accident summary ---
    minor_accidents: int = 0
    major_accidents: int = 0

    # --- auction pricing ---
    starting_price: float = 0.0    # QAR
    current_price: float = 0.0     # QAR (same as starting if no bids)
    min_increment: float = 0.0     # QAR
    bid_count: int = 0
    time_remaining: str = ""       # raw string e.g. "17h 58m 15s"

    # --- market comparison (populated by valuation stage) ---
    market_prices: list[float] = field(default_factory=list)
    market_avg: Optional[float] = None
    market_source: str = ""
    market_sample_count: int = 0

    # --- convenience ---
    @property
    def search_signature(self) -> str:
        """Human-readable key used to query market sites for the same car."""
        parts = [p for p in [self.make, self.model, str(self.year) if self.year else ""] if p]
        return " ".join(parts)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        d["search_signature"] = self.search_signature
        return d

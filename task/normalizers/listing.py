#!/usr/bin/env python3
from task.models import Listing
from task.normalizers.base import BaseNormalizer


class ListingNormalizer(BaseNormalizer):
    """Listing-specific normalization built on shared helpers."""

    def normalize_query(self, value: str) -> str:
        return self.clean_text(value)

    def normalize_name(self, value: str) -> str:
        return self.clean_text(value)

    def normalize_address(self, value: str) -> str:
        return self.clean_text(value)

    def normalize_phone(self, value: str) -> str:
        return self.clean_text(value)

    def normalize_rating(self, value: str) -> str:
        return self.clean_text(value)

    def normalize_website(self, value: str) -> str:
        return self.unwrap_redirect_url(value)

    def normalize_listing(self, listing: Listing) -> Listing:
        return Listing(
            name=self.normalize_name(listing.name),
            lat=listing.lat,
            lon=listing.lon,
            url=self.clean_url(listing.url),
            address=self.normalize_address(listing.address),
            website=self.normalize_website(listing.website),
            rating=self.normalize_rating(listing.rating),
            phone=self.normalize_phone(listing.phone),
            query=self.normalize_query(listing.query),
        )
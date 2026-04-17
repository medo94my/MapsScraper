#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from task.models import Listing
from task.normalizers import ListingNormalizer


class ListingNormalizerFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "listing_normalizer_cases.json"
        cls.cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.normalizer = ListingNormalizer()

    def test_fixture_cases(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["name"]):
                listing = Listing(**case["input"])
                normalized = self.normalizer.normalize_listing(listing)

                for field_name, expected_value in case["expected"].items():
                    self.assertEqual(getattr(normalized, field_name), expected_value)

    def test_dedupe_key_normalizes_equivalent_entities(self) -> None:
        listing_a = Listing(
            name="Royal Razorصالون حلاقه",
            lat=31.954697200,
            lon=35.911830600,
            url="https://maps.google.com/place/a",
            website="/url?q=https://example.com/shop?utm_source=ad&ref=listing",
        )
        listing_b = Listing(
            name="Royal Razor صالون حلاقه",
            lat=31.954697239,
            lon=35.911830639,
            url="https://maps.google.com/place/b",
            website="https://example.com/shop?ref=listing",
        )

        key_a = self.normalizer.dedupe_key(self.normalizer.normalize_listing(listing_a))
        key_b = self.normalizer.dedupe_key(self.normalizer.normalize_listing(listing_b))

        self.assertEqual(key_a, key_b)


if __name__ == "__main__":
    unittest.main()

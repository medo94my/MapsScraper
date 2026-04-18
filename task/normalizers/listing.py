#!/usr/bin/env python3
import re
import unicodedata
from urllib.parse import parse_qs, unquote, urlencode, urlsplit, urlunsplit

from task.models import Listing


class ListingNormalizer:
    """Text and URL normalization for Google Maps listings."""

    _TRACKING_QUERY_KEYS: frozenset[str] = frozenset({
        "fbclid",
        "gclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "opi",
        "sa",
        "source",
        "usg",
        "ved",
    })

    _SCRIPT_BOUNDARY_RE = re.compile(
        r"(?<=[A-Za-z])(?=[\u0600-\u06FF])|(?<=[\u0600-\u06FF])(?=[A-Za-z])"
    )
    _ARABIC_INDIC_DIGIT_MAP = str.maketrans(
        "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
        "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9",
        "01234567890123456789",
    )

    def clean_text(self, value: str) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFC", value)
        filtered = "".join(
            char for char in normalized if not self._is_noise_character(char)
        )
        return re.sub(r"\s+", " ", filtered).strip()

    def _is_noise_character(self, char: str) -> bool:
        if char in {"\n", "\r", "\t", " "}:
            return False
        return unicodedata.category(char) in {"Cc", "Cf", "Co", "Cs"}

    def separate_mixed_scripts(self, value: str) -> str:
        cleaned = self.clean_text(value)
        if not cleaned:
            return ""
        return self._SCRIPT_BOUNDARY_RE.sub(" ", cleaned)

    def clean_url(self, value: str) -> str:
        cleaned = self.clean_text(value)
        if not cleaned:
            return ""

        if cleaned.startswith("www."):
            cleaned = f"https://{cleaned}"

        parts = urlsplit(cleaned)
        if not parts.scheme and parts.netloc:
            parts = urlsplit(f"https://{cleaned}")
        elif not parts.scheme and not parts.netloc and parts.path.startswith("www."):
            parts = urlsplit(f"https://{parts.path}")

        query_pairs = parse_qs(parts.query, keep_blank_values=True)
        filtered_pairs = [
            (key, item)
            for key, values in query_pairs.items()
            if not key.lower().startswith("utm_") and key.lower() not in self._TRACKING_QUERY_KEYS
            for item in values
        ]
        normalized_host = parts.netloc.lower()
        if normalized_host.startswith("www."):
            normalized_host = normalized_host[4:]
        return urlunsplit((
            parts.scheme.lower(),
            normalized_host,
            parts.path,
            urlencode(filtered_pairs, doseq=True),
            "",
        )).strip()

    def unwrap_redirect_url(self, value: str) -> str:
        cleaned = self.clean_url(value)
        if not cleaned:
            return ""
        parsed = urlsplit(cleaned)
        query = parse_qs(parsed.query)
        redirect_target = query.get("q", []) or query.get("url", [])
        if redirect_target:
            return self.clean_url(unquote(redirect_target[0]))
        return cleaned

    def normalize_phone(self, value: str) -> str:
        cleaned = self.clean_text(value)
        if not cleaned:
            return ""
        translated = cleaned.translate(self._ARABIC_INDIC_DIGIT_MAP).replace(" ", "")
        if translated.startswith("00"):
            translated = "+" + translated[2:]
        if translated.startswith("+"):
            digits = re.sub(r"\D", "", translated[1:])
            return f"+{digits}" if digits else ""
        return re.sub(r"\D", "", translated)

    def dedupe_key(self, listing: Listing) -> str:
        normalized_name = self.separate_mixed_scripts(listing.name).casefold()
        normalized_website = self.clean_url(self.unwrap_redirect_url(listing.website))
        website_host = urlsplit(normalized_website).netloc
        lat = round(listing.lat, 5)
        lon = round(listing.lon, 5)
        return f"{normalized_name}|{lat:.5f}|{lon:.5f}|{website_host}"

    def normalize_listing(self, listing: Listing) -> Listing:
        return Listing(
            name=self.separate_mixed_scripts(listing.name),
            lat=listing.lat,
            lon=listing.lon,
            url=self.clean_url(listing.url),
            address=self.separate_mixed_scripts(listing.address),
            website=self.clean_url(self.unwrap_redirect_url(listing.website)),
            rating=self.clean_text(listing.rating),
            phone=self.normalize_phone(listing.phone),
            query=self.clean_text(listing.query),
        )

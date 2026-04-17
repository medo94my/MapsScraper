#!/usr/bin/env python3
import re
import unicodedata
from urllib.parse import parse_qs, unquote, urlsplit


class BaseNormalizer:
    """Reusable text and URL normalization helpers."""

    def clean_text(self, value: str) -> str:
        if not value:
            return ""

        normalized = unicodedata.normalize("NFC", value)
        filtered = "".join(
            char for char in normalized if not self._is_noise_character(char)
        )
        collapsed = re.sub(r"\s+", " ", filtered)
        return collapsed.strip()

    def clean_url(self, value: str) -> str:
        return self.clean_text(value)

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

    def _is_noise_character(self, char: str) -> bool:
        if char in {"\n", "\r", "\t", " "}:
            return False
        return unicodedata.category(char) in {"Cc", "Cf", "Co", "Cs"}
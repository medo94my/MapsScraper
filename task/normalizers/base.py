#!/usr/bin/env python3
import re
import unicodedata
from urllib.parse import parse_qs, unquote, urlencode, urlsplit, urlunsplit


class BaseNormalizer:
    """Reusable text and URL normalization helpers."""

    _TRACKING_QUERY_KEYS = {
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
    }

    _SCRIPT_BOUNDARY_RE = re.compile(
        r"(?<=[A-Za-z])(?=[\u0600-\u06FF])|(?<=[\u0600-\u06FF])(?=[A-Za-z])"
    )
    _ARABIC_INDIC_DIGIT_MAP = str.maketrans(
        "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
        "01234567890123456789",
    )

    def clean_text(self, value: str) -> str:
        if not value:
            return ""

        normalized = unicodedata.normalize("NFC", value)
        filtered = "".join(
            char for char in normalized if not self._is_noise_character(char)
        )
        collapsed = re.sub(r"\s+", " ", filtered)
        return collapsed.strip()

    def separate_mixed_scripts(self, value: str) -> str:
        cleaned = self.clean_text(value)
        if not cleaned:
            return ""
        return self._SCRIPT_BOUNDARY_RE.sub(" ", cleaned)

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
        filtered_pairs = []
        for key, values in query_pairs.items():
            if key.lower().startswith("utm_") or key.lower() in self._TRACKING_QUERY_KEYS:
                continue
            for item in values:
                filtered_pairs.append((key, item))

        normalized_query = urlencode(filtered_pairs, doseq=True)
        normalized_host = parts.netloc.lower()
        if normalized_host.startswith("www."):
            normalized_host = normalized_host[4:]

        normalized = urlunsplit(
            (
                parts.scheme.lower(),
                normalized_host,
                parts.path,
                normalized_query,
                "",
            )
        )
        return normalized.strip()

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
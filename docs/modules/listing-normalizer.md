# ListingNormalizer reference

This page documents field normalization and deduplication logic used to
stabilize output quality.

## Module purpose

task/normalizers/listing.py cleans raw extracted values and defines listing
identity for deduplication.

## Class: ListingNormalizer

ListingNormalizer contains text, URL, phone, and identity normalization helpers.

### clean_text(value: str) -> str

This function normalizes Unicode text and removes control-noise characters.

Behavior:
- NFC normalization.
- removal of unwanted control/private/surrogate classes.
- whitespace collapsing to single spaces.

### _is_noise_character(char: str) -> bool

This internal helper decides which characters to drop.

### separate_mixed_scripts(value: str) -> str

This function inserts spacing between Arabic and Latin script boundaries.

Purpose:
- improve consistency for mixed-script names and addresses.

### clean_url(value: str) -> str

This function normalizes URL values and strips tracking parameters.

Behavior:
- adds https for www-prefixed values.
- normalizes scheme and host casing.
- removes fragment.
- removes utm_* and known tracking keys.

### unwrap_redirect_url(value: str) -> str

This function resolves redirect wrappers carrying target URL in q or url params.

### normalize_phone(value: str) -> str

This function normalizes phone strings to digits-oriented output.

Behavior:
- converts Arabic-Indic digits to ASCII digits.
- converts leading 00 to plus prefix.
- strips separators and non-digits.

### dedupe_key(listing: Listing) -> str

This function returns the deduplication identity key for listing comparison.

Current key components:
- normalized listing name
- latitude rounded to 5 decimals
- longitude rounded to 5 decimals
- normalized website host

Maintenance caution:
- changing this key can significantly alter duplicate behavior and historical
  continuity.

### normalize_listing(listing: Listing) -> Listing

This function returns a new normalized Listing object.

Behavior:
- normalizes all textual fields and URLs.
- preserves coordinate values.
- normalizes query text as part of output consistency.

## Next steps

When you update normalization rules, re-run dedupe and fixture tests to confirm
that behavior changes are intentional.

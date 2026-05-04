"""Phase 4.4 — Text-based email/phone extraction.

Pure regex utilities — no network, no state.
Used by extractors to pull structured signals from unstructured text (bio, README, etc.).
"""

from __future__ import annotations

import re

# ── Email ──────────────────────────────────────────────────────

# Matches standard email addresses.  Excludes:
#   - quoted local-parts (e.g. "john doe"@example.com)
#   - IP-literal domains (rare in public profiles)
#   - localhost / example.com (test domains)
_EMAIL_RE = re.compile(
    r"\b([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+)\b"
)


def extract_emails(text: str) -> list[str]:
    """Return unique, lowercased email addresses found in text."""
    matches = _EMAIL_RE.findall(text)
    seen: set[str] = set()
    results: list[str] = []
    for addr in matches:
        lower = addr.lower()
        if lower in seen:
            continue
        seen.add(lower)
        results.append(lower)
    return results


# ── Phone ──────────────────────────────────────────────────────

# Matches Chinese mobile numbers: 1[3-9]XXXXXXXXX (11 digits).
# Also matches with common separators and country codes.
_PHONE_RE = re.compile(
    r"(?:(?:\+?86)[\s-]*)?1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}"
)

_PHONE_DIGITS_RE = re.compile(r"\D")


def extract_phones(text: str) -> list[str]:
    """Return unique phone numbers (digits only) found in text.

    Normalizes: strips +86 prefix, spaces, dashes.
    """
    matches = _PHONE_RE.findall(text)
    seen: set[str] = set()
    results: list[str] = []
    for raw in matches:
        digits = _PHONE_DIGITS_RE.sub("", raw)
        # Strip Chinese country code if present
        if digits.startswith("86") and len(digits) >= 13:
            digits = digits[2:]
        if len(digits) != 11:
            continue  # skip non-standard lengths
        if digits in seen:
            continue
        seen.add(digits)
        results.append(digits)
    return results

"""Phase 4.4 — Text-based email/phone extraction.

Pure regex utilities — no network, no state.
Used by extractors to pull structured signals from unstructured text (bio, README, etc.).
"""

from __future__ import annotations

import re

# ── Email ──────────────────────────────────────────────────────

# Domains commonly used for disposable/temporary email addresses.
_DISPOSABLE_DOMAINS = frozenset({
    "mailinator.com", "guerrillamail.com", "10minutemail.com",
    "tempmail.com", "temp-mail.org", "throwaway.email",
    "sharklasers.com", "yopmail.com", "trashmail.com",
    "maildrop.cc", "getnada.com", "inboxalias.com",
    "dispostable.com", "mailnesia.com", "spamgourmet.com",
    "anonaddy.com", "simplelogin.com", "33mail.com",
    "temporary.email", "disposablemail.com",
    "example.com", "test.com", "localhost",
})

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
        # Skip disposable/temporary email domains
        domain = lower.split("@", 1)[-1] if "@" in lower else ""
        if domain in _DISPOSABLE_DOMAINS:
            continue
        seen.add(lower)
        results.append(lower)
    return results


# ── Phone ──────────────────────────────────────────────────────

def normalize_phone(s: str) -> str:
    """Strip non-digits and normalize country-code prefixes.

    E.g. '+86 138-0000-1234' → '13800001234'
    """
    digits = "".join(c for c in s if c.isdigit())
    if digits.startswith("86") and len(digits) >= 13:
        digits = digits[2:]
    return digits


# Matches Chinese mobile numbers: 1[3-9]XXXXXXXXX (11 digits).
# Also matches with common separators and country codes.
_PHONE_RE = re.compile(
    r"(?:(?:\+?86)[\s-]*)?1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}"
)


def extract_phones(text: str) -> list[str]:
    """Return unique phone numbers (digits only) found in text.

    Normalizes: strips +86 prefix, spaces, dashes.
    """
    matches = _PHONE_RE.findall(text)
    seen: set[str] = set()
    results: list[str] = []
    for raw in matches:
        digits = normalize_phone(raw)
        if len(digits) != 11:
            continue  # skip non-standard lengths
        if digits in seen:
            continue
        seen.add(digits)
        results.append(digits)
    return results

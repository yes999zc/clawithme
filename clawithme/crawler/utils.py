"""Shared utilities for crawler extractors."""

from __future__ import annotations


def first_text(response, selectors: list[str]) -> str | None:
    """Try each CSS selector, return first non-empty text (stripped)."""
    for sel in selectors:
        result = response.css(sel)
        if result:
            text = " ".join(e.text.strip() for e in result if e.text).strip()
            if text:
                return text
    return None


def parse_count(text: str) -> int | None:
    """Parse '301k', '1.2k', '123' → int. Returns None on failure."""
    text = text.strip().lower().replace(",", "")
    try:
        if text.endswith("k"):
            return int(float(text[:-1]) * 1000)
        return int(text)
    except (ValueError, IndexError):
        return None

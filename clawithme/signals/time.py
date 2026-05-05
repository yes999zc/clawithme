"""Phase 4.x — Time-based correlation signal.

Compares profile joined_dates for identity matching.
"""

from __future__ import annotations

import re

_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date(date_str: str) -> tuple[int, int] | None:
    """Parse a date string to (year, month) or None.

    Handles formats: '2018-03-15', '2018-03', 'Mar 2018', 'March 2018', '2018'.
    Month is 0 when only year is known.
    """
    s = date_str.strip().lower()
    if not s:
        return None

    # "2018-03-15" or "2018-03"
    m = re.match(r"^(\d{4})-(\d{1,2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))

    # "Mar 2018" / "March 2018"
    m = re.match(r"^([a-z]+)\s+(\d{4})$", s)
    if m:
        month = _MONTH_NAMES.get(m.group(1)[:3])
        if month is not None:
            return int(m.group(2)), month

    # "2018" only
    m = re.match(r"^(\d{4})$", s)
    if m:
        return int(m.group(1)), 0

    return None


def compare_joined_dates(date_a: str | None, date_b: str | None) -> float:
    """Return similarity score 0.0–1.0 for two joined_date strings.

    Returns:
      - Same month+year → 0.40
      - Within ±3 months → 0.20
      - Same year only   → 0.10
      - Either None/empty, unparseable, or different years → 0.0
    """
    if not date_a or not date_b or not date_a.strip() or not date_b.strip():
        return 0.0

    pa = _parse_date(date_a)
    pb = _parse_date(date_b)
    if pa is None or pb is None:
        return 0.0

    ya, ma = pa
    yb, mb = pb

    if ya != yb:
        return 0.0

    # Same year — score based on month proximity
    if ma == 0 or mb == 0:
        return 0.10
    if ma == mb:
        return 0.40

    return 0.20 if abs(ma - mb) <= 3 else 0.10

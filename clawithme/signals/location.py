"""Phase 4.x — Location proximity correlation signal.

Compares profile location strings for identity matching.
"""

from __future__ import annotations

# Chinese ↔ English city name mapping
_CITY_MAP: dict[str, str] = {
    "北京": "beijing",
    "上海": "shanghai",
    "广州": "guangzhou",
    "深圳": "shenzhen",
    "杭州": "hangzhou",
    "成都": "chengdu",
    "南京": "nanjing",
    "武汉": "wuhan",
    "重庆": "chongqing",
    "台北": "taipei",
    "香港": "hong kong",
}


def _normalize(loc: str) -> str:
    """Normalize a location string for comparison."""
    s = loc.strip().lower()
    # Normalize known Chinese city names to English
    for cn, en in _CITY_MAP.items():
        if cn in s:
            s = s.replace(cn, en)
    return s


def compare_locations(loc_a: str | None, loc_b: str | None) -> float:
    """Return similarity score 0.0–1.0 for two location strings.

    Returns:
      - Exact match after normalization → 0.35
      - One location is a substring of the other → 0.15
        (e.g., "San Francisco, CA" contains "San Francisco")
      - Either is None/empty → 0.0
    """
    if not loc_a or not loc_b or not loc_a.strip() or not loc_b.strip():
        return 0.0

    a_norm = _normalize(loc_a)
    b_norm = _normalize(loc_b)

    if a_norm == b_norm:
        return 0.35
    if a_norm in b_norm or b_norm in a_norm:
        return 0.15
    return 0.0

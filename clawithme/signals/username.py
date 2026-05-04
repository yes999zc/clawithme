"""Phase 4.x — Username similarity signal.

Compares usernames across platforms using Levenshtein distance
and common affix pattern detection.
"""

from __future__ import annotations


def levenshtein_distance(a: str, b: str) -> int:
    """Standard Levenshtein edit distance."""
    if len(a) < len(b):
        return levenshtein_distance(b, a)
    if len(b) == 0:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(
                curr[-1] + 1,        # insert
                prev[j] + 1,         # delete
                prev[j - 1] + cost,  # replace
            ))
        prev = curr
    return prev[-1]


def compare_usernames(u1: str, u2: str) -> float:
    """Return similarity score 0.0–1.0 for two usernames.

    Handles common patterns:
      - Exact match (case-insensitive) → 1.0
      - Common affix variation (alice / alice_cn / alice_dev)
      - Close Levenshtein distance normalized by max length
    """
    a, b = u1.strip().lower(), u2.strip().lower()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # ── Check for common affix patterns ─────────────────────
    # Strip trailing _cn, _dev, _official, _real, _io
    suffixes = ("_cn", "_dev", "_official", "_real", "_io", "_com", "_org")
    a_stripped = a
    b_stripped = b
    for sfx in suffixes:
        if a_stripped.endswith(sfx):
            a_stripped = a_stripped[:-len(sfx)]
        if b_stripped.endswith(sfx):
            b_stripped = b_stripped[:-len(sfx)]

    if a_stripped and a_stripped == b_stripped:
        return 0.85  # core name matches, only affix differs

    # Strip trailing digits (alice / alice42 / alice123)
    a_alpha = a_stripped.rstrip("0123456789")
    b_alpha = b_stripped.rstrip("0123456789")
    if a_alpha and a_alpha == b_alpha:
        return 0.8  # base name matches, only digit suffix differs

    # ── Levenshtein similarity ──────────────────────────────
    max_len = max(len(a), len(b))
    dist = levenshtein_distance(a, b)
    ratio = 1.0 - (dist / max_len)

    if ratio >= 0.8:
        return round(ratio * 0.7, 2)  # scale down — pure edit distance is weaker
    return 0.0

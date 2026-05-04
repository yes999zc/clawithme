"""Phase 4.3 — Multi-signal correlation engine.

Groups profiles into identity clusters using available signals:
avatar_phash (Hamming distance), email (exact match), phone (exact match).
Uses Union-Find for transitive closure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from clawithme.crawler.base import Profile
from clawithme.signals.avatar import compare_avatars


@dataclass
class Cluster:
    """A group of profiles believed to belong to the same person."""

    profiles: list[Profile]
    confidence: float  # 0.0–1.0, average of strongest signals
    signals: list[str] = field(default_factory=list)  # e.g. ["avatar_phash", "email"]


class CorrelationEngine:
    """Groups profiles by matching signal fingerprints.

    Signals (in order of reliability):
      - email: exact, case-insensitive — weight 1.0
      - phone: exact, digits-only — weight 0.95
      - avatar_phash: Hamming distance ≤ 10 — weight 0.8
    """

    PHASH_THRESHOLD = 10
    SIGNAL_WEIGHTS = {"email": 1.0, "phone": 0.95, "avatar_phash": 0.8}

    def correlate(self, profiles: list[Profile]) -> list[Cluster]:
        """Return clusters. Each profile belongs to exactly one cluster."""
        n = len(profiles)
        if n <= 1:
            return [Cluster(profiles=profiles, confidence=1.0, signals=[])]

        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        # ── Compare all pairs ──────────────────────────────────
        for i in range(n):
            for j in range(i + 1, n):
                pi, pj = profiles[i], profiles[j]
                if self._signals_match(pi, pj):
                    union(i, j)

        # ── Extract clusters ───────────────────────────────────
        groups: dict[int, list[int]] = {}
        for i in range(n):
            root = find(i)
            groups.setdefault(root, []).append(i)

        clusters: list[Cluster] = []
        for indices in groups.values():
            cluster_profiles = [profiles[i] for i in indices]
            confidence = 1.0 if len(indices) == 1 else self._cluster_confidence(
                cluster_profiles
            )
            clusters.append(
                Cluster(
                    profiles=cluster_profiles,
                    confidence=round(confidence, 2),
                    signals=self._detected_signals(cluster_profiles),
                )
            )

        return clusters

    # ── Private ────────────────────────────────────────────────

    def _signals_match(self, a: Profile, b: Profile) -> bool:
        """True if any signal definitively links two profiles."""
        return (
            (a.avatar_phash and b.avatar_phash and compare_avatars(
                a.avatar_phash, b.avatar_phash, self.PHASH_THRESHOLD
            )["is_match"])
            or (a.email and b.email and a.email.strip().lower() == b.email.strip().lower())
            or (a.phone and b.phone and _phone_digits(a.phone) == _phone_digits(b.phone))
        )

    def _cluster_confidence(self, profiles: list[Profile]) -> float:
        """Average of strongest matching signal weights."""
        weights: list[float] = []
        for i in range(len(profiles)):
            for j in range(i + 1, len(profiles)):
                pi, pj = profiles[i], profiles[j]
                w = self._pair_confidence(pi, pj)
                if w > 0:
                    weights.append(w)
        return sum(weights) / len(weights) if weights else 0.0

    def _pair_confidence(self, a: Profile, b: Profile) -> float:
        """Highest signal weight that matches between two profiles."""
        best = 0.0
        if a.email and b.email and a.email.strip().lower() == b.email.strip().lower():
            best = max(best, self.SIGNAL_WEIGHTS["email"])
        if a.phone and b.phone and _phone_digits(a.phone) == _phone_digits(b.phone):
            best = max(best, self.SIGNAL_WEIGHTS["phone"])
        if a.avatar_phash and b.avatar_phash and compare_avatars(
            a.avatar_phash, b.avatar_phash, self.PHASH_THRESHOLD
        )["is_match"]:
            best = max(best, self.SIGNAL_WEIGHTS["avatar_phash"])
        return best

    def _detected_signals(self, profiles: list[Profile]) -> list[str]:
        """Which signals contributed to this cluster."""
        seen: list[str] = []
        if any(p.avatar_phash for p in profiles):
            seen.append("avatar_phash")
        if any(p.email for p in profiles):
            seen.append("email")
        if any(p.phone for p in profiles):
            seen.append("phone")
        return seen


def _phone_digits(s: str) -> str:
    """Strip non-digits and normalize common country-code prefixes.

    E.g. '+86 138-0000-1234' → '13800001234'
    """
    digits = "".join(c for c in s if c.isdigit())
    # Strip Chinese country code
    if digits.startswith("86") and len(digits) >= 13:
        digits = digits[2:]
    return digits

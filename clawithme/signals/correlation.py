"""Phase 4.3 — Multi-signal correlation engine.

Groups profiles into identity clusters using available signals:
avatar_phash (Hamming distance), email (exact match), phone (exact match).
Uses Union-Find for transitive closure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clawithme.crawler.base import Profile
from clawithme.signals.avatar import compare_avatars
from clawithme.signals.extraction import normalize_phone
from clawithme.signals.location import compare_locations
from clawithme.signals.time import compare_joined_dates
from clawithme.signals.username import compare_usernames, levenshtein_distance

if TYPE_CHECKING:
    from clawithme.signals.llm_verifier import LLMVerifier


@dataclass
class Cluster:
    """A group of profiles believed to belong to the same person."""

    profiles: list[Profile]
    confidence: float  # 0.0–1.0, average of strongest signals
    signals: list[str] = field(default_factory=list)  # e.g. ["avatar_phash", "email"]
    evidence: dict[str, list[str]] = field(default_factory=dict)
    # evidence: {signal_name: ["siteA ↔ siteB: value", ...]}


class CorrelationEngine:
    """Groups profiles by matching signal fingerprints.

    Signals (in order of reliability):
      - email: exact, case-insensitive — weight 1.0
      - phone: exact, digits-only — weight 0.95
      - avatar_phash: Hamming distance ≤ 10 — weight 0.8

    If *llm_verifier* is provided, high-conflict cases (username match
    contradicted by display_name/location) are escalated to LLM arbitration.
    """

    PHASH_THRESHOLD = 10
    USERNAME_THRESHOLD = 0.80
    SIGNAL_WEIGHTS = {
        "email": 1.0,
        "phone": 0.95,
        "avatar_phash": 0.8,
        "username": 0.7,
        "joined_date": 0.15,
        "location": 0.15,
    }

    def __init__(self, llm_verifier: "LLMVerifier | None" = None) -> None:
        self._llm = llm_verifier

    def correlate(self, profiles: list[Profile]) -> list[Cluster]:  # noqa: PLR0912
        """Return clusters. Each profile belongs to exactly one cluster."""
        n = len(profiles)
        if n == 0:
            return []
        if n == 1:
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
        matched_edges: list[tuple[int, int, set[str]]] = []
        edge_evidence: dict[tuple[int, int], dict[str, str]] = {}
        for i in range(n):
            for j in range(i + 1, n):
                pi, pj = profiles[i], profiles[j]
                sigs = self._match_signals(pi, pj)
                if sigs:
                    union(i, j)
                    matched_edges.append((i, j, sigs))
                    evidence_map: dict[str, str] = {}
                    if "email" in sigs:
                        evidence_map["email"] = pi.email or ""
                    if "phone" in sigs:
                        evidence_map["phone"] = normalize_phone(pi.phone or "")
                    if "avatar_phash" in sigs:
                        match = compare_avatars(
                            pi.avatar_phash, pj.avatar_phash, self.PHASH_THRESHOLD
                        )
                        evidence_map["avatar_phash"] = f"distance={match.distance}"
                    if "username" in sigs:
                        sim = compare_usernames(pi.username, pj.username)
                        evidence_map["username"] = f"{pi.username} ↔ {pj.username} (sim={sim:.2f})"
                    if "joined_date" in sigs:
                        score = compare_joined_dates(pi.joined_date, pj.joined_date)
                        evidence_map["joined_date"] = (
                            f"{pi.joined_date} ↔ {pj.joined_date} "
                            f"(score={score:.2f})"
                        )
                    if "location" in sigs:
                        score = compare_locations(pi.location, pj.location)
                        evidence_map["location"] = (
                            f"{pi.location} ↔ {pj.location} "
                            f"(score={score:.2f})"
                        )
                    edge_evidence[(i, j)] = evidence_map

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
            # Collect evidence from edges within this cluster
            idx_set = set(indices)
            cluster_evidence: dict[str, list[str]] = {}
            for (i, j), ev in edge_evidence.items():
                if i in idx_set and j in idx_set:
                    for sig, detail in ev.items():
                        cluster_evidence.setdefault(sig, []).append(detail)
            clusters.append(
                Cluster(
                    profiles=cluster_profiles,
                    confidence=round(confidence, 2),
                    signals=self._detected_signals(indices, matched_edges),
                    evidence=cluster_evidence,
                )
            )

        return clusters

    # ── Private ────────────────────────────────────────────────

    def _match_signals(self, a: Profile, b: Profile) -> set[str]:
        """Return signal names that matched between two profiles. Empty set = no match."""
        matched: set[str] = set()
        if (a.avatar_phash and b.avatar_phash and compare_avatars(
                a.avatar_phash, b.avatar_phash, self.PHASH_THRESHOLD
        ).is_match):
            matched.add("avatar_phash")
        if (a.email and b.email and
                a.email.strip().lower() == b.email.strip().lower()):
            matched.add("email")
        if (a.phone and b.phone and
                normalize_phone(a.phone) == normalize_phone(b.phone)):
            matched.add("phone")
        sim = compare_usernames(a.username, b.username)
        if sim >= self.USERNAME_THRESHOLD:
            if self._is_username_contradicted(a, b):
                # High-conflict — escalate to LLM if available
                if self._llm is not None and self._llm.is_configured():
                    is_same, confidence, _ = self._llm.verify_same_person(a, b)
                    if is_same and confidence >= self._llm.CONFIDENCE_THRESHOLD:
                        matched.add("username")
                # If no LLM or LLM says DIFFERENT: don't add username signal
            else:
                matched.add("username")
        if compare_joined_dates(a.joined_date, b.joined_date) > 0:
            matched.add("joined_date")
        if compare_locations(a.location, b.location) > 0:
            matched.add("location")

        # Anti-merge: username-only match requires stronger evidence
        if matched == {"username"} and not self._is_strong_username_match(a, b):
            matched.discard("username")

        return matched

    def _is_strong_username_match(self, a: Profile, b: Profile) -> bool:
        """Check if a username-only link has enough evidence to merge.

        Username-only matches are the weakest signal — common short
        names like 'alex' or 'john' can belong to different people.
        Gating logic:
          1. Long usernames (>=8 chars) are unique enough → always merge
          2. Affix/pattern variants (0.85-0.94, e.g. 'alice' vs 'alice_cn')
             indicate conscious identity demarcation → merge
          3. Exact match (>=0.95) on short name → need display-name consensus
        """
        if len(a.username) >= 8:
            return True
        sim = compare_usernames(a.username, b.username)
        # Affix/pattern variants — conscious identity demarcation
        if 0.85 <= sim < 0.95:
            return True
        # Exact match on short name — need human confirmation
        if sim >= 0.95:
            if a.display_name and b.display_name:
                dn_sim = compare_usernames(
                    a.display_name.strip().lower(),
                    b.display_name.strip().lower(),
                )
                if dn_sim >= 0.5:
                    return True
            # Same location supports same-person hypothesis
            return bool(
                a.location and b.location and
                a.location.strip().lower() == b.location.strip().lower()
            )
        return False

    def _is_username_contradicted(self, a: Profile, b: Profile) -> bool:
        """Username match is contradicted when display_name and location differ sharply."""
        if not a.display_name or not b.display_name:
            return False
        if not a.location or not b.location:
            return False
        if a.location.strip().lower() == b.location.strip().lower():
            return False
        da = a.display_name.strip().lower()
        db = b.display_name.strip().lower()
        max_len = max(len(da), len(db))
        if max_len == 0:
            return False
        dn_sim = 1.0 - (levenshtein_distance(da, db) / max_len)
        return dn_sim < 0.3

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
        sigs = self._match_signals(a, b)
        if not sigs:
            return 0.0
        return max(self.SIGNAL_WEIGHTS[s] for s in sigs)

    def _detected_signals(self, indices: list[int],
                          matched_edges: list[tuple[int, int, set[str]]]) -> list[str]:
        """Return signal names that actually contributed to this cluster."""
        idx_set = set(indices)
        sigs: set[str] = set()
        for i, j, edge_sigs in matched_edges:
            if i in idx_set and j in idx_set:
                sigs.update(edge_sigs)
        return sorted(sigs)

"""Crawler base — Profile dataclass and ProfileExtractor ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Profile:
    """Unified profile data extracted from a single site.

    All fields optional — different sites expose different data.
    """

    site_id: str
    site_name: str
    url: str
    username: str
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    avatar_phash: str | None = None  # perceptual hash for cross-platform avatar matching (Phase 4)
    email: str | None = None  # Phase 4.3 — from leak sources or extractors
    phone: str | None = None  # Phase 4.3 — from leak sources or extractors
    location: str | None = None
    joined_date: str | None = None
    post_count: int | None = None
    follower_count: int | None = None
    following_count: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        """True if no meaningful data beyond site id/name/url/username."""
        return not any([
            self.display_name, self.bio, self.avatar_url,
            self.avatar_phash, self.email, self.phone,
            self.location, self.joined_date,
            self.post_count, self.follower_count is not None,
            self.following_count is not None, self.extra,
        ])


class ProfileExtractor(ABC):
    """Abstract base for site-specific profile crawlers.

    Each extractor handles ONE site. Registered via entry_points
    under group 'clawithme.extractors'.
    """

    # Must be set by subclass
    site_id: str = ""

    # Set to True if DynamicFetcher (Playwright) is REQUIRED
    requires_dynamic: bool = False

    @abstractmethod
    def extract(self, site: dict, username: str) -> Profile:
        """Crawl the site and return a Profile."""
        ...

    # ── Default dispatch logic ─────────────────────────────────

    def can_handle(self, site: dict) -> bool:
        """Return True if this extractor matches the site.

        Default: checks site['id'] == self.site_id.
        Override for complex routing (e.g. match by engine or category).
        """
        return site.get("id") == self.site_id

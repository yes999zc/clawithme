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
    avatar_hash: str | None = None  # sha256 of avatar image
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
            self.location, self.joined_date, self.post_count,
            self.follower_count, self.extra,
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
    def can_handle(self, site: dict) -> bool:
        """Return True if this extractor can handle the given site dict."""
        ...

    @abstractmethod
    def extract(self, site: dict, username: str) -> Profile:
        """Crawl the site and return a Profile."""
        ...

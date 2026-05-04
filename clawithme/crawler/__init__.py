"""Phase 3 — Deep crawler: profile extraction framework."""

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient, random_user_agent
from clawithme.crawler.registry import discover_extractors

__all__ = [
    "Profile", "ProfileExtractor", "CrawlerClient",
    "random_user_agent", "discover_extractors",
]

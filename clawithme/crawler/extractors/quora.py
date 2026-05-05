"""Quora profile extractor — static HTML from quora.com/profile pages.

Quora may redirect; we handle 404 and "Page not found" gracefully.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class QuoraExtractor(ProfileExtractor):
    """Extract public profile data from Quora."""

    site_id = "quora"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.quora.com/profile/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Quora"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None:
                return profile

            # Quora returns 404 for missing profiles
            if response.status in (404, 410):
                return profile

            text = response.text or ""
            # Handle "Page not found"
            if "Page not found" in text or "404" in text:
                return profile

            # Display name
            name = first_text(response, [
                "h1[class*=\"profile\"]",
                "span[class*=\"profile\"]",
                "[class*=\"profileHeader\"] h1",
                "[class*=\"name\"]",
            ])
            if name:
                profile.display_name = name

            # Bio
            bio = first_text(response, [
                "[class*=\"description\"]",
                "[class*=\"bio\"]",
                "[class*=\"about\"]",
            ])
            if bio:
                profile.bio = bio

            logger.debug("quora_extracted", username=username, display_name=profile.display_name)
        finally:
            client.close()

        return profile

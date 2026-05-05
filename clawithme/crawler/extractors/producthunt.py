"""Product Hunt profile extractor — static HTML from producthunt.com.

Product Hunt profiles are JS-rendered; we extract what's available
from server-rendered content gracefully.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class ProducthuntExtractor(ProfileExtractor):
    """Extract public profile data from Product Hunt."""

    site_id = "producthunt"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.producthunt.com/@{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Product Hunt"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None:
                return profile

            # PH returns non-200 for missing profiles
            if response.status in (404, 410):
                return profile

            # Display name
            name = first_text(response, [
                "[class*=\"userName\"]",
                "[class*=\"name\"]",
                "[class*=\"displayName\"]",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Bio
            bio = first_text(response, [
                "[class*=\"bio\"]",
                "[class*=\"description\"]",
                "[class*=\"tagline\"]",
            ])
            if bio:
                profile.bio = bio

            logger.debug("producthunt_extracted", username=username,
                          display_name=profile.display_name)
        finally:
            client.close()

        return profile

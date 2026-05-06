"""Instagram profile extractor — best-effort static fetch.

URL: https://www.instagram.com/{username}/
Instagram is a SPA with Login walls. Most extraction methods fail.
This extractor tries og:meta tags and gracefully returns empty on failure.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class InstagramExtractor(ProfileExtractor):
    """Extract public profile data from Instagram (best-effort)."""

    site_id = "instagram"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.instagram.com/{username}/"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Instagram"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Try og:title for display name
            tag = response.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                import re
                title = tag[0].attrib["content"]
                clean = re.sub(r"^@\S+\s*[•·]\s*", "", title).strip()
                if clean:
                    profile.display_name = clean

            # Try og:image for avatar
            tag = response.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src

        finally:
            client.close()

        return profile

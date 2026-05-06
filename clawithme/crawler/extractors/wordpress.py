"""WordPress.com profile extractor — static HTML + meta tags.

URL: https://{username}.wordpress.com
WordPress.com blog profiles render server-side.
We parse display_name, avatar_url, bio from meta tags.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class WordpressExtractor(ProfileExtractor):
    """Extract public profile data from WordPress.com."""

    site_id = "wordpress"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://{username}.wordpress.com"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "WordPress"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Display name from og:title
            tag = response.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                profile.display_name = tag[0].attrib["content"].strip()

            # Avatar from og:image
            tag = response.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src

            # Bio from og:description
            tag = response.css("meta[property='og:description']")
            if tag and tag[0].attrib.get("content"):
                bio = tag[0].attrib["content"].strip()
                if bio:
                    profile.bio = bio

        finally:
            client.close()

        return profile

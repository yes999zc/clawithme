"""Blogger (Blogspot) profile extractor — static HTML + meta tags.

URL: https://{username}.blogspot.com
Blogger profiles render server-side. Parses meta tags.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class BloggerExtractor(ProfileExtractor):
    """Extract public profile data from Blogger."""

    site_id = "blogger"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://{username}.blogspot.com"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Blogger"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            tag = response.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                profile.display_name = tag[0].attrib["content"].strip()

            tag = response.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src

            tag = response.css("meta[property='og:description']")
            if tag and tag[0].attrib.get("content"):
                bio = tag[0].attrib["content"].strip()
                if bio:
                    profile.bio = bio

        finally:
            client.close()

        return profile

"""Instagram profile extractor — static HTML + meta tags.

URL: https://www.instagram.com/{username}/
Instagram renders og:title, og:image meta tags in static HTML.
We parse: display_name from og:title, avatar_url from og:image.
"""

from __future__ import annotations

import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class InstagramExtractor(ProfileExtractor):
    """Extract public profile data from Instagram via og:meta tags."""

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

            # Display name from og:title
            # Format: "陈丹 (@oadank) • Instagram photos and videos"
            tag = response.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                title = tag[0].attrib["content"]
                # Strip trailing " • Instagram photos and videos"
                clean = re.sub(r"\s*[•·]\s*Instagram.*$", "", title).strip()
                # Remove parenthesized username
                clean = re.sub(r"\s*\(@\S+\)\s*", "", clean).strip()
                if clean:
                    profile.display_name = clean

            # Avatar from og:image
            tag = response.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src

        finally:
            client.close()

        return profile

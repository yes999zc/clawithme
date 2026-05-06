"""Goodreads profile extractor — og:meta tags.

URL: https://www.goodreads.com/{username}
Goodreads renders server-side profile pages.
We parse: display_name, avatar_url, bio from og:meta.
"""

from __future__ import annotations

import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class GoodreadsExtractor(ProfileExtractor):
    """Extract public profile data from Goodreads."""

    site_id = "goodreads"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.goodreads.com/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Goodreads"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            html = response.text or ""

            # Display name
            m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
            if m:
                title = m.group(1)
                clean = re.sub(r"\s*[-–|]\s*Goodreads$", "", title).strip()
                if clean:
                    profile.display_name = clean

            # Avatar
            m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
            if m:
                src = m.group(1)
                if not src.startswith("data:"):
                    profile.avatar_url = src

            # Bio
            m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
            if m:
                desc = m.group(1)
                if desc and "profile" not in desc.lower():
                    profile.bio = desc

        finally:
            client.close()

        return profile

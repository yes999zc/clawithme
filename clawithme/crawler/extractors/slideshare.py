"""SlideShare profile extractor — static HTML.

URL: https://www.slideshare.net/{username}
SlideShare renders server-side profile pages.
We parse: display_name, avatar_url, bio, follower_count.
"""

from __future__ import annotations

import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class SlideshareExtractor(ProfileExtractor):
    """Extract public profile data from SlideShare."""

    site_id = "slideshare"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.slideshare.net/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "SlideShare"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            html = response.text or ""

            # Display name from og:title
            tag = response.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                title = tag[0].attrib["content"]
                # Format: "username's Profile"
                clean = re.sub(r"'s\s*Profile$", "", title).strip()
                if clean:
                    profile.display_name = clean

            # Avatar
            for sel in ("meta[property='og:image']", "meta[name='twitter:image']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    src = tag[0].attrib["content"]
                    if not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Bio from og:description
            tag = response.css("meta[property='og:description']")
            if tag and tag[0].attrib.get("content"):
                desc = tag[0].attrib["content"].strip()
                # Strip "View username..." prefix
                clean = re.sub(r"^View\s+@?\S+\'?s?\s+", "", desc)
                profile.bio = (clean or desc) if desc else None

            # Location from page text
            location = first_text(response, [
                "[class*='location']",
                "[class*='country']",
                "span[class*='locality']",
            ])
            if location:
                profile.location = location

            # Follower count
            m = re.search(r"(\d[\d,]*)\s*follower", html, re.IGNORECASE)
            if m:
                profile.follower_count = int(m.group(1).replace(",", ""))

        finally:
            client.close()

        return profile

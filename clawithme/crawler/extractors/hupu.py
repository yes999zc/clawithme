"""Hupu (虎扑) profile extractor — static HTML.

URL: https://my.hupu.com/{username}
Hupu renders server-side profile pages.
We parse: display_name, avatar_url, bio.
"""

from __future__ import annotations

import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class HupuExtractor(ProfileExtractor):
    """Extract public profile data from Hupu."""

    site_id = "hupu"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://my.hupu.com/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "虎扑"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            html = response.text or ""

            # Display name from title
            title = first_text(response, ["title"])
            if title:
                clean = re.sub(r"\s*[-–|]\s*虎扑.*$", "", title).strip()
                if clean:
                    profile.display_name = clean

            # Avatar
            for sel in (".avatar img", ".user-avatar img", "img.avatar",
                        "img[class*='avatar']"):
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        if src.startswith("//"):
                            src = "https:" + src
                        profile.avatar_url = src
                        break

            # Bio
            desc = first_text(response, [
                ".user-desc",
                ".profile-bio",
                "[class*='description']",
                "[class*='signature']",
            ])
            if desc:
                profile.bio = desc

            # Follower count
            m = re.search(r"(\d[\d,]*)\s*粉丝", html)
            if m:
                profile.follower_count = int(m.group(1).replace(",", ""))

        finally:
            client.close()

        return profile

"""酷安 (coolapk) profile extractor — static HTML.

URL: https://www.coolapk.com/u/{uid}
酷安 user profiles use server-rendered HTML.
Note: coolapk may require special headers or cookies in some cases.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class CoolapkExtractor(ProfileExtractor):
    """Extract public profile data from 酷安 (coolapk)."""

    site_id = "coolapk"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.coolapk.com/u/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "酷安"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Display name
            name = first_text(response, [
                ".user-name",
                ".space-user-name",
                "h1[class*=\"name\"]",
                "[class*=\"username\"]",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Bio
            bio = first_text(response, [
                "[class*=\"bio\"]",
                "[class*=\"description\"]",
                "[class*=\"intro\"]",
                "[class*=\"sign\"]",
            ])
            if bio:
                profile.bio = bio

            # Avatar
            for sel in [
                "img.avatar",
                ".avatar img",
                "[class*=\"avatar\"] img",
            ]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Followers
            follower_text = first_text(response, [
                "[class*=\"follower\"] span",
                "[class*=\"follow\"] span",
                "[class*=\"fans\"] span",
            ])
            if follower_text:
                profile.follower_count = parse_count(follower_text)

        finally:
            client.close()

        return profile

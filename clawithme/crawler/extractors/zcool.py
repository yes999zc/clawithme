"""站酷 Zcool profile extractor — static HTML.

URL: https://www.zcool.com.cn/u/{username}
Zcool designer profiles use server-rendered HTML.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class ZcoolExtractor(ProfileExtractor):
    """Extract public profile data from 站酷 (Zcool)."""

    site_id = "zcool"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.zcool.com.cn/u/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "站酷"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            page_text = response.text or ""
            if "用户不存在" in page_text:
                return profile

            # Display name
            name = first_text(response, [
                ".user-name",
                ".author-name",
                "h1[class*=\"name\"]",
                ".user-info-name",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Bio / tagline
            bio = first_text(response, [
                ".user-desc",
                ".author-desc",
                ".user-info-desc",
                "[class*=\"description\"]",
                "[class*=\"intro\"]",
            ])
            if bio:
                profile.bio = bio

            # Avatar
            for sel in [
                "img.avatar",
                ".user-avatar img",
                ".author-avatar img",
                "[class*=\"avatar\"] img",
            ]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Follower count
            follower_text = first_text(response, [
                ".follow-num",
                "[class*=\"follower\"] span",
                "[class*=\"follow\"] .num",
                ".user-stat .num",
            ])
            if follower_text:
                profile.follower_count = parse_count(follower_text)

            # Location
            location = first_text(response, [
                ".user-location",
                "[class*=\"location\"]",
                ".user-info-location",
            ])
            if location:
                profile.location = location

        finally:
            client.close()

        return profile

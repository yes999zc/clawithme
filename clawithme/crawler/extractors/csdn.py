"""CSDN profile extractor — static HTML.

URL: https://blog.csdn.net/{username}
CSDN blog profiles use server-rendered HTML.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class CsdnExtractor(ProfileExtractor):
    """Extract public profile data from CSDN blog."""

    site_id = "csdn"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://blog.csdn.net/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "CSDN"),
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
                "h1.user-profile-title",
                ".user-name",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Bio / personal description
            bio = first_text(response, [
                ".user-profile-bio",
                ".profile-bio",
                ".desc",
            ])
            if bio:
                profile.bio = bio

            # Avatar
            for sel in [
                "img.avatar-pic",
                ".avatar img",
                "img[class*=\"avatar\"]",
                ".user-profile-avatar img",
            ]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Followers — find the stat item whose name contains "粉丝" (fans)
            stat_items = response.css(".user-profile-statistics-item")
            for item in stat_items:
                name_el = item.css(".user-profile-statistics-name")
                count_el = item.css(".count")
                if name_el and count_el and "粉丝" in (name_el[0].text or ""):
                    count_text = (count_el[0].text or "").strip()
                    if count_text:
                        profile.follower_count = parse_count(count_text)
                    break

        finally:
            client.close()

        return profile

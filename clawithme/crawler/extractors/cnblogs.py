"""博客园 (cnblogs) profile extractor — static HTML.

URL: https://www.cnblogs.com/{username}
博客园 blog profiles use server-rendered HTML.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class CnblogsExtractor(ProfileExtractor):
    """Extract public profile data from 博客园 (cnblogs)."""

    site_id = "cnblogs"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.cnblogs.com/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "博客园"),
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
                ".profile_username",
                "#header_user_left a",
                "h1",
                "[class*=\"username\"]",
            ])
            if name:
                profile.display_name = name

            # Bio
            bio = first_text(response, [
                ".profile_description",
                "[class*=\"description\"]",
                "[class*=\"intro\"]",
            ])
            if bio:
                profile.bio = bio

            # Avatar
            for sel in [
                "img.profile_avatar",
                ".profile_avatar img",
                "img[class*=\"avatar\"]",
                "#profile_avatar img",
            ]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Followers
            follower_text = first_text(response, [
                ".profile_followers",
                "[class*=\"follower\"]",
                "[class*=\"follow\"] span",
            ])
            if follower_text:
                profile.follower_count = parse_count(follower_text)

        finally:
            client.close()

        return profile

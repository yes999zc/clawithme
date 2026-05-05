"""简书 (jianshu) profile extractor — static HTML.

URL: https://www.jianshu.com/u/{hash_or_username}
简书 user profiles use server-rendered HTML.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class JianshuExtractor(ProfileExtractor):
    """Extract public profile data from 简书 (jianshu)."""

    site_id = "jianshu"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.jianshu.com/u/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "简书"),
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
                ".name",
                "h1[class*=\"name\"]",
                "[class*=\"user\"] [class*=\"name\"]",
                "h1.title",
            ])
            if name:
                profile.display_name = name

            # Bio
            bio = first_text(response, [
                ".info ul li",
                "[class*=\"bio\"]",
                "[class*=\"description\"]",
                "[class*=\"signature\"]",
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
                ".follower span",
                "[class*=\"follower\"] span",
                "[class*=\"follow\"] span",
            ])
            if follower_text:
                profile.follower_count = parse_count(follower_text)

            # Following
            following_text = first_text(response, [
                ".following span",
                "[class*=\"following\"] span",
            ])
            if following_text:
                profile.following_count = parse_count(following_text)

        finally:
            client.close()

        return profile

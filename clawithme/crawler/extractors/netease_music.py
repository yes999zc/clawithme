"""网易云音乐 Netease Music profile extractor — static HTML.

URL: https://music.163.com/user/home?id={username}
Netease Music user profiles may require the page to be fetched with proper headers.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class NeteaseMusicExtractor(ProfileExtractor):
    """Extract public profile data from 网易云音乐 (Netease Music)."""

    site_id = "netease_music"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://music.163.com/user/home?id={username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "网易云音乐"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            page_text = response.text or ""
            # Non-existent user may show an error page
            if ("该用户不存在" in page_text or "找不到该用户" in page_text
                    or "User doesn't exist" in page_text):
                return profile

            # Display name
            name = first_text(response, [
                ".user-name",
                ".nickname",
                "h1[class*=\"name\"]",
                ".user-info .name",
                ".tit",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Bio / signature
            bio = first_text(response, [
                ".signature",
                ".user-desc",
                "[class*=\"bio\"]",
                ".user-info-desc",
            ])
            if bio:
                profile.bio = bio

            # Avatar
            for sel in [
                "img.head",
                ".head img",
                ".user-head img",
                ".avatar img",
                "[class*=\"avatar\"] img",
                ".user-info .head img",
            ]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Follower count
            follower_text = first_text(response, [
                "[class*=\"follower\"] .num",
                "[class*=\"follow\"] .num",
                ".user-stat .follower span",
            ])
            if follower_text:
                profile.follower_count = parse_count(follower_text)

            # Following count
            following_text = first_text(response, [
                "[class*=\"following\"] .num",
                ".user-stat .following span",
            ])
            if following_text:
                profile.following_count = parse_count(following_text)

        finally:
            client.close()

        return profile

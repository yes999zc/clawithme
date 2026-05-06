"""Tieba (百度贴吧) profile extractor — static HTML.

URL: https://tieba.baidu.com/home/main?un={username}
Baidu Tieba renders server-side profile pages.
We parse: display_name, avatar_url, bio, follower_count.
"""

from __future__ import annotations

import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class TiebaExtractor(ProfileExtractor):
    """Extract public profile data from Baidu Tieba."""

    site_id = "tieba"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://tieba.baidu.com/home/main?un={username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "贴吧"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            html = response.text or ""

            # Display name from page title: "username的个人主页"
            title = first_text(response, ["title"])
            if title:
                clean = re.sub(r"的个人主页.*$", "", title).strip()
                if clean:
                    profile.display_name = clean

            # Avatar from image with user name
            for sel in (".user-head img", ".user_info_head img",
                        "img[class*='head']", ".avatar img"):
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        if src.startswith("//"):
                            src = "https:" + src
                        profile.avatar_url = src
                        break

            # Bio from user description
            desc = first_text(response, [
                ".user_desc",
                ".user-desc",
                "[class*='description']",
            ])
            if desc:
                profile.bio = desc

            # Follower count from stats
            m = re.search(r"粉丝[：:]\s*(\d+)", html)
            if m:
                profile.follower_count = int(m.group(1))

            # Post count
            m = re.search(r"帖子[：:]\s*(\d+)", html)
            if m:
                profile.post_count = int(m.group(1))

        finally:
            client.close()

        return profile

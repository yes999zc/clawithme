"""百度知道 Baidu Zhidao profile extractor — static HTML (GBK encoding).

URL: https://zhidao.baidu.com/usercenter?uid={username}
Baidu pages may use GBK encoding.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class BaiduZhidaoExtractor(ProfileExtractor):
    """Extract public profile data from 百度知道 (Baidu Zhidao)."""

    site_id = "baidu_zhidao"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://zhidao.baidu.com/usercenter?uid={username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "百度知道"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # GBK encoding check for absence string
            raw = response.body if isinstance(response.body, bytes) else b""
            page_text = raw.decode("gbk", errors="replace") if raw else response.text
            if "没有找到该用户哦～" in page_text:
                return profile

            # Display name
            name = first_text(response, [
                ".user-name",
                ".nickname",
                ".user-name-txt",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Avatar
            for sel in [
                "img.user-pic",
                ".user-head img",
                ".avatar img",
                "img[class*=\"avatar\"]",
            ]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Follower/following count (usually "被采纳数" or similar stats)
            for item in response.css(".stat-item, .user-stat-item, .num-item"):
                text = item.text.strip() if item.text else ""
                if text and text.isdigit():
                    count = parse_count(text)
                    if count and profile.follower_count is None:
                        profile.follower_count = count

        finally:
            client.close()

        return profile

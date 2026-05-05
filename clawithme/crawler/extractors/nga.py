"""NGA profile extractor — static HTML (GBK encoding).

URL: https://bbs.nga.cn/nuke.php?func=ucp&username={username}
NGA uses GBK encoding.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class NgaExtractor(ProfileExtractor):
    """Extract public profile data from NGA (bbs.nga.cn)."""

    site_id = "nga"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://bbs.nga.cn/nuke.php?func=ucp&username={username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "NGA"),
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
            if "找不到用户" in page_text or "用户信息不存在" in page_text:
                return profile

            # Display name (often repeated in the UCP page header)
            name = first_text(response, [
                ".ucp-username",
                ".username",
                ".poster-info span",
                "h2",
            ])
            if name:
                profile.display_name = name

            # Avatar
            for sel in [
                ".ucp-avatar img",
                ".avatar img",
                "img[class*=\"avatar\"]",
                ".poster-avatar img",
            ]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Joined date
            date_text = first_text(response, [
                ".ucp-regdate",
                "[class*=\"regdate\"]",
                "[class*=\"register\"]",
            ])
            if date_text:
                profile.joined_date = date_text.strip()

        finally:
            client.close()

        return profile

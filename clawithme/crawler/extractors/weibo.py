"""Weibo (微博) profile extractor — static HTML + meta tags.

URL: https://weibo.com/u/{username}
Weibo renders server-side meta tags for crawlers.
We parse: display_name (nickname), avatar_url, bio, follower_count.
"""

from __future__ import annotations

import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class WeiboExtractor(ProfileExtractor):
    """Extract public profile data from Weibo."""

    site_id = "weibo"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        # Try both URL formats — /u/{uid} and /{username}
        url = f"https://weibo.com/u/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "微博"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                # Fallback: try /{username} format
                url2 = f"https://weibo.com/{username}"
                response = client.fetch_static(url2)
                if response is None or response.status != 200:
                    return profile
                profile.url = url2

            html = response.text or ""
            if not html:
                return profile

            # Display name from page title: "username的微博"
            title_text = first_text(response, ["title"])
            if title_text:
                clean = re.sub(r"的微博.*$", "", title_text).strip()
                if clean:
                    profile.display_name = clean

            # Avatar from og:image
            for sel in ("meta[property='og:image']", "meta[name='twitter:image']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    src = tag[0].attrib["content"]
                    if not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Bio from description
            desc = first_text(response, ["meta[name='description']"])
            if desc:
                # Weibo description format: "username，...简介... 微博..."
                clean = re.sub(r"微博$", "", desc).strip()
                if clean and clean != title_text:
                    profile.bio = clean

            # Follower count from script data
            m = re.search(r'"followers_count"\s*:\s*(\d+)', html)
            if m:
                profile.follower_count = int(m.group(1))

            m = re.search(r'"friends_count"\s*:\s*(\d+)', html)
            if m:
                profile.following_count = int(m.group(1))

            m = re.search(r'"statuses_count"\s*:\s*(\d+)', html)
            if m:
                profile.post_count = int(m.group(1))

        finally:
            client.close()

        return profile

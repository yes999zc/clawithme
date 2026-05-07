"""TikTok profile extractor — static HTML + inline JSON data.

URL: https://www.tiktok.com/@{username}
Extracts: display_name, bio, avatar_url, follower_count, following_count.
"""

from __future__ import annotations

import json
import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class TiktokExtractor(ProfileExtractor):
    """Extract public profile data from TikTok."""

    site_id = "tiktok"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.tiktok.com/@{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "TikTok"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            page_text = response.text or ""

            # ── Extract from __NEXT_DATA__ ──
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>\s*({.*?})\s*</script>', page_text, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    # Navigate to user data
                    props = data.get("props", {}).get("pageProps", {})
                    user = props.get("userData", {}).get("user", props.get("user", {}))
                    if not user:
                        user = props.get("userInfo", {}).get("user", {})

                    if user:
                        profile.display_name = user.get("nickname") or profile.display_name
                        profile.bio = (user.get("signature") or user.get("bio") or "")[:500] or profile.bio
                        profile.follower_count = _to_int(user.get("followerCount") or user.get("follower_count"))
                        profile.following_count = _to_int(user.get("followingCount") or user.get("following_count"))
                        profile.post_count = _to_int(user.get("videoCount") or user.get("aweme_count"))
                        avatar = user.get("avatarLarger") or user.get("avatarMedium") or user.get("avatarThumb") or user.get("avatar_url")
                        if avatar and not avatar.startswith("data:"):
                            profile.avatar_url = avatar
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

            # ── Fallback: og:meta tags ──
            if not profile.display_name:
                tag = response.css("meta[property='og:title']")
                if tag and tag[0].attrib.get("content"):
                    profile.display_name = tag[0].attrib["content"].strip()

            if not profile.avatar_url:
                tag = response.css("meta[property='og:image']")
                if tag and tag[0].attrib.get("content"):
                    src = tag[0].attrib["content"]
                    if not src.startswith("data:"):
                        profile.avatar_url = src

        finally:
            client.close()

        return profile


def _to_int(val) -> int | None:
    """Convert a value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

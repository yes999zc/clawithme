"""Pinterest profile extractor — static HTML + meta tags + JSON data.

URL: https://www.pinterest.com/{username}/
Extracts: display_name, bio, avatar_url, follower_count.
"""

from __future__ import annotations

import json
import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class PinterestExtractor(ProfileExtractor):
    """Extract public profile data from Pinterest."""

    site_id = "pinterest"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.pinterest.com/{username}/"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Pinterest"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            page_text = response.text or ""

            # ── Display name from og:title ──
            tag = response.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                title = tag[0].attrib["content"].strip()
                if title:
                    profile.display_name = title

            # ── Avatar from og:image ──
            tag = response.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src

            # ── Bio from og:description or description meta ──
            tag = response.css("meta[name='description']")
            if tag and tag[0].attrib.get("content"):
                desc = tag[0].attrib["content"].strip()
                if desc:
                    profile.bio = desc[:500]

            # ── Parse inline JSON for stats ──
            # Pinterest embeds user data in a script tag
            m = re.search(r'<script[^>]*data-test-id="user-profile"[^>]*data-pin-user="([^"]+)"', page_text)
            if m:
                try:
                    import html
                    user_data = json.loads(html.unescape(m.group(1)))
                    if user_data:
                        fc = user_data.get("follower_count") or user_data.get("followerCount")
                        if fc is not None:
                            profile.follower_count = int(fc)
                        if not profile.display_name:
                            profile.display_name = user_data.get("full_name") or user_data.get("username")
                        if not profile.avatar_url:
                            av = user_data.get("image_medium_url") or user_data.get("image_xlarge_url")
                            if av and not av.startswith("data:"):
                                profile.avatar_url = av
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

            # ── Fallback: JSON-LD block ──
            if not profile.follower_count:
                for script in response.css("script[type=\"application/ld+json\"]"):
                    try:
                        data = json.loads(script.text)
                        if isinstance(data, dict):
                            author = data.get("author", {})
                            fc = author.get("followerCount")
                            if fc is not None:
                                profile.follower_count = int(fc)
                            break
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue

        finally:
            client.close()

        return profile

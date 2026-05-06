"""LeetCode profile extractor — og:meta tags + JSON-LD.

URL: https://leetcode.com/u/{username}/
LeetCode renders server-side profile pages with og:meta and JSON-LD.
We parse: display_name, avatar_url, bio from og:meta tags.
"""

from __future__ import annotations

import json
import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class LeetcodeExtractor(ProfileExtractor):
    """Extract public profile data from LeetCode."""

    site_id = "leetcode"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://leetcode.com/u/{username}/"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "LeetCode"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            html = response.text or ""
            if not html:
                return profile

            # Display name from og:title
            m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
            if m:
                title = m.group(1)
                # Format: "username - LeetCode Profile"
                clean = re.sub(r"\s*[-–|]\s*LeetCode.*$", "", title).strip()
                if clean:
                    profile.display_name = clean

            # Avatar from og:image
            m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
            if m:
                src = m.group(1)
                if not src.startswith("data:"):
                    profile.avatar_url = src

            # Bio from og:description
            m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
            if m:
                desc = m.group(1)
                if desc and "LeetCode Profile" not in desc:
                    profile.bio = desc

            # Try JSON-LD for additional data
            for m2 in re.finditer(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                html, re.DOTALL,
            ):
                try:
                    data = json.loads(m2.group(1))
                    if isinstance(data, dict):
                        if not profile.display_name:
                            profile.display_name = data.get("name") or None
                        if not profile.avatar_url:
                            img = data.get("image", "")
                            if img and not img.startswith("data:"):
                                profile.avatar_url = img
                except (json.JSONDecodeError, AttributeError):
                    continue

        finally:
            client.close()

        return profile

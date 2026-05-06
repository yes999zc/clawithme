"""Instagram profile extractor — static HTML + meta tags + embedded JSON-LD.

URL: https://www.instagram.com/{username}/
Instagram renders server-side HTML with meta tags and JSON-LD for crawlers.
We parse: display_name (og:title), avatar_url (og:image), bio, follower_count.
"""

from __future__ import annotations

import json
import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class InstagramExtractor(ProfileExtractor):
    """Extract public profile data from Instagram."""

    site_id = "instagram"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.instagram.com/{username}/"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Instagram"),
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

            # Display name from og:title (format: "@username • photos/videos")
            for sel in ("meta[property='og:title']", "meta[name='twitter:title']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    title = tag[0].attrib["content"]
                    # Strip "@username •" prefix
                    clean = re.sub(r"^@\S+\s*[•·]\s*", "", title)
                    profile.display_name = clean.strip()
                    break

            # Avatar from og:image
            for sel in ("meta[property='og:image']", "meta[name='twitter:image']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    src = tag[0].attrib["content"]
                    if not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Try to parse JSON-LD for bio and stats
            for script in response.css("script[type='application/ld+json']"):
                try:
                    data = json.loads(script.text_content() or "{}")
                    if isinstance(data, dict) and data.get("@type") == "ProfilePage":
                        author = data.get("author", {})
                        if isinstance(author, dict):
                            if not profile.display_name:
                                profile.display_name = author.get("name", "")
                            if not profile.avatar_url:
                                profile.avatar_url = author.get("image", "")
                            profile.bio = author.get("description", "") or None
                            # Follower count from interactionStatistic
                            stats = data.get("interactionStatistic", [])
                            for s in stats if isinstance(stats, list) else []:
                                if s.get("interactionType") == "FollowAction":
                                    profile.follower_count = s.get("userInteractionCount")
                                    break
                        break
                except (json.JSONDecodeError, AttributeError):
                    continue

            # Fallback: try __INITIAL_STATE__ in <script> for follower count
            if profile.follower_count is None:
                m = re.search(
                    r'"edge_followed_by"\s*:\s*{\s*"count"\s*:\s*(\d+)',
                    html,
                )
                if m:
                    profile.follower_count = int(m.group(1))

        finally:
            client.close()

        return profile

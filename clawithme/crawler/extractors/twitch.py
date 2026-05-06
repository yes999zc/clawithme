"""Twitch profile extractor — static HTML + meta tags.

URL: https://www.twitch.tv/{username}
Twitch renders server-side meta tags for crawlers.
We parse: display_name, avatar_url, bio, follower_count.
"""

from __future__ import annotations

import json
import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class TwitchExtractor(ProfileExtractor):
    """Extract public profile data from Twitch."""

    site_id = "twitch"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.twitch.tv/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Twitch"),
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

            # Display name from og:title or twitter:title
            for sel in ("meta[property='og:title']", "meta[name='twitter:title']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    title = tag[0].attrib["content"]
                    # Twitch format: "username - Twitch"
                    clean = re.sub(r"\s*[-–|]\s*Twitch$", "", title).strip()
                    if clean:
                        profile.display_name = clean
                    break

            # Avatar from og:image
            for sel in ("meta[property='og:image']", "meta[name='twitter:image']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    src = tag[0].attrib["content"]
                    if not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Bio from og:description
            tag = response.css("meta[property='og:description']")
            if tag and tag[0].attrib.get("content"):
                bio = tag[0].attrib["content"].strip()
                # Strip "Watch username's..." prefix
                clean = re.sub(r"^Watch\s+@?\S+\'?s?\s+", "", bio)
                if clean and clean != bio:
                    profile.bio = clean.strip()
                else:
                    profile.bio = bio

            # Follower count from JSON-LD
            for script in response.css("script[type='application/ld+json']"):
                try:
                    data = json.loads(script.text_content() or "{}")
                    if isinstance(data, dict):
                        stats = data.get("interactionStatistic", [])
                        for s in stats if isinstance(stats, list) else []:
                            if s.get("interactionType") == "FollowAction":
                                profile.follower_count = s.get("userInteractionCount")
                                break
                except (json.JSONDecodeError, AttributeError):
                    continue

        finally:
            client.close()

        return profile

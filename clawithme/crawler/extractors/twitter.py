"""Twitter/X profile extractor — static HTML + meta tags + JSON-LD.

URL: https://twitter.com/{username} (or x.com/{username})
Twitter renders server-side meta tags for crawlers.
We parse: display_name (og:title), avatar_url (og:image), bio (og:description).
"""

from __future__ import annotations

import json
import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class TwitterExtractor(ProfileExtractor):
    """Extract public profile data from Twitter/X."""

    site_id = "twitter"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://twitter.com/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Twitter/X"),
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

            # Display name from og:title (format: "@username • Display Name")
            for sel in ("meta[property='og:title']", "meta[name='twitter:title']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    title = tag[0].attrib["content"]
                    # Strip "@username •" prefix
                    clean = re.sub(r"^@\S+\s*[•·]\s*", "", title)
                    profile.display_name = clean.strip()
                    break

            # Avatar from og:image or twitter:image
            for sel in ("meta[property='og:image']", "meta[name='twitter:image']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    src = tag[0].attrib["content"]
                    if not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Bio from og:description (also contains follower/location info)
            for sel in ("meta[property='og:description']", "meta[name='description']"):
                tag = response.css(sel)
                if tag and tag[0].attrib.get("content"):
                    desc = tag[0].attrib["content"]
                    # Strip trailing "username.github.io • ... followers • ... following"
                    clean = re.sub(
                        r"\s•\s+\d+[KkMmBb]?\s*(Followers|Following).*$", "", desc
                    )
                    clean = re.sub(r"\s•\s+.*\.(com|io|org|net)\s*.*$", "", clean)
                    if clean.strip():
                        profile.bio = clean.strip()
                    break

            # Follower count from JSON-LD or __NEXT_DATA__
            for script in response.css("script[type='application/ld+json']"):
                try:
                    data = json.loads(script.text_content() or "{}")
                    if isinstance(data, dict) and data.get("@type") == "ProfilePage":
                        stats = data.get("mainEntityofPage", {}).get(
                            "interactionStatistic", []
                        )
                        if isinstance(stats, list):
                            for s in stats:
                                if s.get("interactionType") == "FollowAction":
                                    profile.follower_count = s.get(
                                        "userInteractionCount"
                                    )
                        break
                except (json.JSONDecodeError, AttributeError):
                    continue

            # Fallback: regex for follower count in script bundles
            if profile.follower_count is None:
                m = re.search(
                    r'"followers_count"\s*:\s*(\d+)',
                    html,
                )
                if m:
                    profile.follower_count = int(m.group(1))

        finally:
            client.close()

        return profile

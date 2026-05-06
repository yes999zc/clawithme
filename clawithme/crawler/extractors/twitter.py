"""Twitter/X profile extractor — dynamic fetch via Playwright (SPA).

URL: https://x.com/{username} or https://twitter.com/{username}
Twitter/X no longer renders profile meta tags in static HTML (SPA shell).
Uses DynamicFetcher (Playwright) to render JS and parse the page content.
"""

from __future__ import annotations

import json
import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class TwitterExtractor(ProfileExtractor):
    """Extract public profile data from Twitter/X (dynamic fetch)."""

    site_id = "twitter"
    requires_dynamic = True

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://x.com/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Twitter/X"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=20000)
        try:
            response = client.fetch_dynamic(url)
            if response is None or response.status != 200:
                return profile

            html = str(response.html_content) if response.html_content else ""
            if not html or len(html) < 3000:
                return profile

            # Twitter embeds user data in __NEXT_DATA__ JSON
            m = re.search(
                r'<script id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>'
                r'(.*?)</script>',
                html, re.DOTALL,
            )
            if not m:
                # Try alternative: window.__INITIAL_STATE__
                m = re.search(
                    r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
                    html, re.DOTALL,
                )
            if not m:
                return profile

            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                return profile

            # __INITIAL_STATE__ path: entities.users.entities.{user_id}
            users_map = (
                data.get("entities", {})
                .get("users", {})
                .get("entities", {})
            )
            # Find user by matching screen_name
            for uid, user_data in users_map.items():
                if isinstance(user_data, dict) and user_data.get("screen_name", "").lower() == username.lower():
                    user = user_data
                    break
            else:
                user = None

            if not user:
                return profile

            profile.display_name = user.get("name") or None
            profile.bio = user.get("description") or None
            profile.avatar_url = user.get("profile_image_url_https") or None
            profile.follower_count = user.get("followers_count")
            profile.following_count = user.get("friends_count")
            profile.post_count = user.get("statuses_count")
            profile.location = user.get("location") or None

        finally:
            client.close()

        return profile

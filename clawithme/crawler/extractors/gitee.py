"""Gitee (码云) profile extractor — public API, no auth.

API: https://gitee.com/api/v5/users/{username}
Returns JSON with: name, avatar_url, bio, followers_count, following_count.
No authentication needed.
"""

from __future__ import annotations

import json
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.logging import get_logger

logger = get_logger()


class GiteeExtractor(ProfileExtractor):
    """Extract public profile data from Gitee via REST API."""

    site_id = "gitee"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        api_url = f"https://gitee.com/api/v5/users/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Gitee"),
            url=f"https://gitee.com/{username}",
            username=username,
        )

        try:
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "clawithme/1.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            profile.display_name = data.get("name") or None
            profile.bio = data.get("bio") or None
            profile.avatar_url = data.get("avatar_url") or None
            profile.follower_count = data.get("followers_count")
            profile.following_count = data.get("following_count")

        except (OSError, json.JSONDecodeError) as e:
            logger.debug("gitee_api_failed", username=username, error=str(e))

        return profile

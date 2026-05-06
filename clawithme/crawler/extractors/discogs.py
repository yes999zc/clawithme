"""Discogs profile extractor — public API.

API: https://api.discogs.com/users/{username}
Returns JSON with: username, name, avatar_url, location, rank, joined.
No authentication needed for basic profile.
"""

from __future__ import annotations

import json
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.logging import get_logger

logger = get_logger()


class DiscogsExtractor(ProfileExtractor):
    """Extract public profile data from Discogs via API."""

    site_id = "discogs"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        api_url = f"https://api.discogs.com/users/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Discogs"),
            url=f"https://www.discogs.com/user/{username}",
            username=username,
        )

        try:
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "clawithme/1.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            profile.display_name = data.get("name") or data.get("username") or None
            profile.avatar_url = data.get("avatar_url") or None
            profile.location = data.get("location") or None
            profile.bio = data.get("profile") or None
            profile.follower_count = data.get("num_public")
            profile.email = data.get("email") or None

        except (OSError, json.JSONDecodeError) as e:
            logger.debug("discogs_api_failed", username=username, error=str(e))

        return profile

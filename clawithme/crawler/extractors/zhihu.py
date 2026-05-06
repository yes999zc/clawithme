"""Zhihu (知乎) profile extractor — public API, no auth.

API: https://www.zhihu.com/api/v4/members/{username}
Returns JSON with: name, avatar_url, headline (bio), gender, follower_count.
No authentication needed.
"""

from __future__ import annotations

import json
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger
from clawithme.signals.avatar import compute_phash

logger = get_logger()


class ZhihuExtractor(ProfileExtractor):
    """Extract public profile data from Zhihu via REST API."""

    site_id = "zhihu"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        api_url = f"https://www.zhihu.com/api/v4/members/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "知乎"),
            url=f"https://www.zhihu.com/people/{username}",
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
            profile.bio = data.get("headline") or None
            profile.avatar_url = data.get("avatar_url") or \
                data.get("avatar_url_template", "").replace("{size}", "l") or None
            # Compute perceptual hash from avatar for cross-platform matching
            if profile.avatar_url:
                try:
                    avatar_resp = urllib.request.urlopen(
                        urllib.request.Request(profile.avatar_url, headers={"User-Agent": "clawithme/1.0"}),
                        timeout=5,
                    )
                    profile.avatar_phash = compute_phash(avatar_resp.read())
                except (OSError, ValueError) as e:
                    logger.debug("zhihu_avatar_phash_failed", username=username, error=str(e))
            profile.location = data.get("location") or None
            profile.follower_count = data.get("follower_count") or \
                data.get("followerCount") or None
            profile.following_count = data.get("following_count") or \
                data.get("followingCount") or None

        except (OSError, json.JSONDecodeError) as e:
            logger.debug("zhihu_api_failed", username=username, error=str(e))

        return profile

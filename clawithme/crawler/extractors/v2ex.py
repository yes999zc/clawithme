"""V2EX profile extractor — API-based, no JS rendering needed.

V2EX API v1: https://www.v2ex.com/api/members/show.json?username={username}
Returns JSON with: id, username, website, twitter, github, location, tagline, bio,
avatar URLs (multiple sizes), created (unix timestamp), status.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import UTC, datetime

from clawithme.crawler.base import Profile, ProfileExtractor

logger = logging.getLogger(__name__)


class V2exExtractor(ProfileExtractor):
    """Extract profile data from v2ex.com member API."""

    site_id = "v2ex"

    def can_handle(self, site_def: dict) -> bool:
        return site_def.get("id") == "v2ex"

    def extract(self, site_def: dict, username: str) -> Profile:
        api_url = f"https://www.v2ex.com/api/members/show.json?username={username}"
        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "clawithme/1.0",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            if data.get("status") == "found":
                created_ts = data.get("created")
                joined = (
                    datetime.fromtimestamp(created_ts, tz=UTC).strftime("%Y-%m-%d")
                    if created_ts
                    else None
                )
                # Collect cross-platform links
                links = {}
                for field in ("github", "twitter", "website"):
                    val = data.get(field, "")
                    if val:
                        links[field] = val

                return Profile(
                    site_id=self.site_id,
                    site_name="V2EX",
                    url=f"https://www.v2ex.com/member/{username}",
                    username=username,
                    display_name=data.get("username", username),
                    bio=data.get("bio") or data.get("tagline") or None,
                    avatar_url=data.get("avatar_large"),
                    location=data.get("location") or None,
                    joined_date=joined,
                    extra=links if links else {},
                )

            # User not found or status != "found"
            return Profile(
                site_id=self.site_id,
                site_name="V2EX",
                url=f"https://www.v2ex.com/member/{username}",
                username=username,
            )
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"v2ex_parse_failed username={username} error={e}")
            return Profile(
                site_id=self.site_id,
                site_name="V2EX",
                url=f"https://www.v2ex.com/member/{username}",
                username=username,
            )

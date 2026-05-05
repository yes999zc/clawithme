"""dev.to profile extractor — public REST API, no auth needed.

API: GET https://dev.to/api/users/by_username?url={username}
Returns a JSON object with full profile data.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor

logger = logging.getLogger(__name__)


class DevtoExtractor(ProfileExtractor):
    """Extract profile data from dev.to public API."""

    site_id = "devto"

    def can_handle(self, site_def: dict) -> bool:
        return site_def.get("id") == "devto"

    def extract(self, site_def: dict, username: str) -> Profile:
        api_url = (
            "https://dev.to/api/users/by_username"
            f"?url={urllib.request.quote(username)}"
        )
        base_profile = Profile(
            site_id=self.site_id,
            site_name="dev.to",
            url=f"https://dev.to/{username}",
            username=username,
        )

        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "clawithme/1.0",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            if not data or "username" not in data:
                return base_profile

            # Cross-platform links
            links = {}
            for field in ("twitter_username", "github_username", "website_url"):
                val = data.get(field, "")
                if val:
                    links[field.replace("_username", "")] = val

            return Profile(
                site_id=self.site_id,
                site_name="dev.to",
                url=f"https://dev.to/{data.get('username', username)}",
                username=username,
                display_name=data.get("name"),
                bio=data.get("summary") or None,
                avatar_url=data.get("profile_image"),
                location=data.get("location") or None,
                joined_date=data.get("joined_at"),
                extra=links if links else {},
            )
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"devto_parse_failed username={username} error={e}")
            return base_profile

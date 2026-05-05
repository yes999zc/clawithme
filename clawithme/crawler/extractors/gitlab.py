"""GitLab profile extractor — public REST API, no auth needed.

API: GET https://gitlab.com/api/v4/users?username={username}
Returns a JSON array; first element is the matched user.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor

logger = logging.getLogger(__name__)


class GitlabExtractor(ProfileExtractor):
    """Extract profile data from gitlab.com public API."""

    site_id = "gitlab"

    def can_handle(self, site_def: dict) -> bool:
        return site_def.get("id") == "gitlab"

    def extract(self, site_def: dict, username: str) -> Profile:
        api_url = (
            f"https://gitlab.com/api/v4/users"
            f"?username={urllib.request.quote(username)}"
        )
        base_profile = Profile(
            site_id=self.site_id,
            site_name="GitLab",
            url=f"https://gitlab.com/{username}",
            username=username,
        )

        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "clawithme/1.0",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            if not data or not isinstance(data, list):
                return base_profile

            user = data[0]

            if user.get("username", "").lower() != username.lower():
                return base_profile

            extra = {}
            for field in ("twitter", "linkedin", "web_url", "bio"):
                val = user.get(field)
                if val:
                    extra[field] = val

            return Profile(
                site_id=self.site_id,
                site_name="GitLab",
                url=user.get("web_url") or base_profile.url,
                username=username,
                display_name=user.get("name"),
                bio=user.get("bio") or None,
                avatar_url=user.get("avatar_url"),
                location=user.get("location") or None,
                extra=extra if extra else {},
            )
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"gitlab_parse_failed username={username} error={e}")
            return base_profile

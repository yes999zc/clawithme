"""StackOverflow profile extractor — StackExchange public API, no auth needed.

API: GET https://api.stackexchange.com/2.3/users
     ?order=desc&sort=reputation&inname={username}&site=stackoverflow

Default response includes: display_name, profile_image, location, website_url,
reputation, creation_date, badge_counts. No custom filter needed.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import UTC, datetime

from clawithme.crawler.base import Profile, ProfileExtractor

logger = logging.getLogger(__name__)


class StackoverflowExtractor(ProfileExtractor):
    """Extract profile data from StackOverflow via StackExchange public API."""

    site_id = "stackoverflow"

    def can_handle(self, site_def: dict) -> bool:
        return site_def.get("id") == "stackoverflow"

    def extract(self, site_def: dict, username: str) -> Profile:
        # StackExchange API returns default fields: display_name, profile_image,
        # location, website_url, reputation, creation_date, badge_counts
        api_url = (
            "https://api.stackexchange.com/2.3/users"
            "?order=desc&sort=reputation"
            f"&inname={urllib.request.quote(username)}"
            "&site=stackoverflow"
        )
        base_profile = Profile(
            site_id=self.site_id,
            site_name="StackOverflow",
            url=f"https://stackoverflow.com/users/{username}",
            username=username,
        )

        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "clawithme/1.0",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            items = data.get("items", [])
            if not items:
                return base_profile

            # Prefer exact display_name match, fallback to first result
            user = None
            for item in items:
                if item.get("display_name", "").lower() == username.lower():
                    user = item
                    break
            if user is None:
                user = items[0]

            user_id = user.get("user_id")
            so_url = (
                f"https://stackoverflow.com/users/{user_id}/{username}"
                if user_id
                else base_profile.url
            )

            created_ts = user.get("creation_date")
            joined = (
                datetime.fromtimestamp(created_ts, tz=UTC).strftime("%Y-%m-%d")
                if created_ts
                else None
            )

            extra = {}
            if user.get("reputation"):
                extra["reputation"] = user["reputation"]
            if user.get("website_url"):
                extra["website"] = user["website_url"]
            badge_counts = user.get("badge_counts", {})
            if badge_counts:
                extra["badges"] = badge_counts

            return Profile(
                site_id=self.site_id,
                site_name="StackOverflow",
                url=so_url,
                username=username,
                display_name=user.get("display_name"),
                bio=None,  # SO default API doesn't expose about_me
                avatar_url=user.get("profile_image"),
                location=user.get("location") or None,
                joined_date=joined,
                extra=extra if extra else {},
            )
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"stackoverflow_parse_failed username={username} error={e}")
            return base_profile

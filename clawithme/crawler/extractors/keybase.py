"""Keybase profile extractor — public REST API, no auth needed.

API: GET https://keybase.io/_/api/1.0/user/lookup.json?usernames={username}
Returns JSON with basics, profile (bio, avatar, location), proofs_summary.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor

logger = logging.getLogger(__name__)


class KeybaseExtractor(ProfileExtractor):
    """Extract profile data from Keybase public API."""

    site_id = "keybase"

    def can_handle(self, site_def: dict) -> bool:
        return site_def.get("id") == "keybase"

    def extract(self, site_def: dict, username: str) -> Profile:
        api_url = (
            "https://keybase.io/_/api/1.0/user/lookup.json"
            f"?usernames={urllib.request.quote(username)}"
        )
        base_profile = Profile(
            site_id=self.site_id,
            site_name="Keybase",
            url=f"https://keybase.io/{username}",
            username=username,
        )

        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "clawithme/1.0",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            status = data.get("status", {})
            if status.get("code") != 0:
                return base_profile

            them = data.get("them", [])
            if not them or them[0] is None:
                return base_profile

            user = them[0]
            if not isinstance(user, dict):
                return base_profile
            basics = user.get("basics", {})
            profile = user.get("profile", {})

            display_name = basics.get("display_name") or basics.get("username_cased") or basics.get("username") or username

            # Social proofs → extra
            proofs = user.get("proofs_summary", {}) or {}
            proofs_extra = {}
            for proof_type in ("twitter", "github", "reddit", "hackernews", "website"):
                val = proofs.get(proof_type)
                if val:
                    proofs_extra[proof_type] = val

            return Profile(
                site_id=self.site_id,
                site_name="Keybase",
                url=f"https://keybase.io/{username}",
                username=username,
                display_name=str(display_name),
                bio=profile.get("bio") or None,
                avatar_url=profile.get("avatar_url") or None,
                location=profile.get("location") or None,
                extra=proofs_extra if proofs_extra else {},
            )
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("keybase_parse_failed", extra={"username": username, "error": str(e)})
            return base_profile

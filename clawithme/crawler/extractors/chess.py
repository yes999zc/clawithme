"""Chess.com profile extractor — public API.

API: https://api.chess.com/pub/player/{username}
Returns JSON with: username, name, avatar, location, followers, joined.
No authentication needed.
"""

from __future__ import annotations

import json
import urllib.request
from contextlib import suppress
from datetime import datetime

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.logging import get_logger

logger = get_logger()


class ChessExtractor(ProfileExtractor):
    """Extract public profile data from Chess.com via API."""

    site_id = "chess"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        api_url = f"https://api.chess.com/pub/player/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Chess.com"),
            url=f"https://www.chess.com/member/{username}",
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
            profile.avatar_url = data.get("avatar") or None
            profile.location = data.get("location") or None
            profile.follower_count = data.get("followers")

            joined = data.get("joined")
            if joined:
                with suppress(OSError, ValueError):
                    profile.joined_date = datetime.fromtimestamp(joined).strftime("%Y-%m-%d")

        except (OSError, json.JSONDecodeError) as e:
            logger.debug("chess_api_failed", username=username, error=str(e))

        return profile

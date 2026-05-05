"""Bilibili profile extractor — API-based, no JS rendering needed.

Uses Bilibili web-interface card API:
  https://api.bilibili.com/x/web-interface/card?mid={uid}

Bilibili usernames are NOT the same as user IDs (mid). The probe URL uses mid,
so we need to handle the mid lookup. Currently the site JSON uses uid-based probing;
this extractor assumes site_def provides the mid.

Alternatively, we can use the space API to resolve username → mid:
  https://api.bilibili.com/x/web-interface/search/type?keyword={username}&search_type=bili_user
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from datetime import UTC, datetime

from clawithme.crawler.base import Profile, ProfileExtractor

logger = logging.getLogger(__name__)

# Bilibili UID extraction from space URL
_UID_RE = re.compile(r"space\.bilibili\.com/(\d+)")


class BilibiliExtractor(ProfileExtractor):
    """Extract Bilibili profile via public web-interface card API."""

    site_id = "bilibili"

    def can_handle(self, site_def: dict) -> bool:
        return site_def.get("id") == "bilibili"

    def extract(self, site_def: dict, username: str) -> Profile:
        # Bilibili API requires numeric UID. If username is text, resolve via search.
        mid = username if username.isdigit() else self._search_mid(username)
        if not mid:
            return Profile.empty(site_id=self.site_id)

        api_url = f"https://api.bilibili.com/x/web-interface/card?mid={mid}"
        try:
            req = urllib.request.Request(api_url, headers={
                "Referer": "https://www.bilibili.com",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            if data.get("code") != 0:
                code = data.get("code")
                msg = data.get("message", "")
                logger.info(f"bilibili_api_error code={code} msg={msg}")
                return Profile.empty(site_id=self.site_id)

            card = data.get("data", {}).get("card", {})
            if not card:
                return Profile.empty(site_id=self.site_id)

            display_name = card.get("name") or username
            sign = card.get("sign") or None
            face = card.get("face")
            fans = card.get("fans")
            attention = card.get("attention")
            sex = card.get("sex")
            official = card.get("Official", {})
            official_title = official.get("title") if official else None

            # Collect extra fields
            extra = {}
            if sex:
                extra["gender"] = sex
            if official_title:
                extra["verified"] = official_title

            return Profile(
                site_id=self.site_id,
                site_name="Bilibili",
                url=f"https://space.bilibili.com/{mid}",
                username=username,
                display_name=display_name,
                bio=sign,
                avatar_url=face,
                follower_count=fans,
                following_count=attention,
                extra=extra if extra else {},
            )
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"bilibili_parse_failed username={username} error={e}")
            return Profile.empty(site_id=self.site_id)

    @staticmethod
    def _search_mid(username: str) -> str | None:
        """Resolve text username to numeric UID via search API."""
        import urllib.parse
        import urllib.request

        try:
            query = urllib.parse.quote(username)
            url = (
                "https://api.bilibili.com/x/web-interface/search/type"
                f"?keyword={query}&search_type=bili_user"
            )
            req = urllib.request.Request(url, headers={
                "Referer": "https://www.bilibili.com",
                "User-Agent": "Mozilla/5.0",
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            results = data.get("data", {}).get("result", [])
            if results:
                return str(results[0].get("mid"))
        except (OSError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"bilibili_search_mid_failed username={username} error={e}")
        return None

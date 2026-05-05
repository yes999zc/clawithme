"""豆瓣 Douban profile extractor — public REST API, no auth needed.

API: GET https://api.douban.com/v2/user/{username}
Returns a JSON object with basic profile data.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor

logger = logging.getLogger(__name__)


class DoubanExtractor(ProfileExtractor):
    """Extract profile data from Douban public API."""

    site_id = "douban"

    def can_handle(self, site_def: dict) -> bool:
        return site_def.get("id") == "douban"

    def extract(self, site_def: dict, username: str) -> Profile:
        api_url = f"https://api.douban.com/v2/user/{urllib.parse.quote(username)}"
        base_profile = Profile(
            site_id=self.site_id,
            site_name=site_def.get("name", "豆瓣"),
            url=f"https://www.douban.com/people/{username}/",
            username=username,
        )

        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            if not data or "id" not in data or data.get("msg") == "user_not_found":
                return base_profile

            return Profile(
                site_id=self.site_id,
                site_name=site_def.get("name", "豆瓣"),
                url=f"https://www.douban.com/people/{data.get('uid', username)}/",
                username=username,
                display_name=data.get("name"),
                bio=data.get("signature") or None,
                avatar_url=data.get("avatar"),
                joined_date=data.get("created"),
            )
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.info(f"douban_user_not_found username={username}")
            else:
                logger.warning(f"douban_http_error username={username} code={e.code}")
            return base_profile
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"douban_parse_failed username={username} error={e}")
            return base_profile

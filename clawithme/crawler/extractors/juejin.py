"""掘金 Juejin profile extractor — CSS first (static), API as fallback.

Profile page: https://juejin.cn/user/{username}
API: https://api.juejin.cn/user_api/v1/user/get?user_id={username} (numeric IDs only)
"""

from __future__ import annotations

import json
import logging
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()
_api_logger = logging.getLogger(__name__)


class JuejinExtractor(ProfileExtractor):
    """Extract public profile data from Juejin (掘金)."""

    site_id = "juejin"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://juejin.cn/user/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "掘金"),
            url=url,
            username=username,
        )

        # Step 1: Try CSS extraction from static HTML
        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response and response.status == 200:
                profile = self._extract_css(response, site, username, url)
                if profile.display_name:
                    return profile
        finally:
            client.close()

        # Step 2: Fall back to API (numeric user_id only)
        if username.isdigit():
            profile = self._extract_api(site, username)
            if profile.display_name:
                return profile

        return Profile(
            site_id=self.site_id,
            site_name=site.get("name", "掘金"),
            url=url,
            username=username,
        )

    def _extract_css(
        self, response, site: dict, username: str, url: str,
    ) -> Profile:
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "掘金"),
            url=url,
            username=username,
        )

        page_text = response.text
        if "用户不存在" in page_text:
            return profile

        name = first_text(response, [
            "h1.username",
            ".user-name",
            "h1.user-info-name",
            "title",
        ])
        if name:
            profile.display_name = name

        bio = first_text(response, [
            ".description",
            ".user-bio",
            ".user-desc",
        ])
        if bio:
            profile.bio = bio

        for sel in ["img.avatar", ".user-avatar img", "[class*=\"avatar\"] img"]:
            imgs = response.css(sel)
            if imgs:
                src = imgs[0].attrib.get("src", "")
                if src and not src.startswith("data:"):
                    profile.avatar_url = src
                    break

        return profile

    def _extract_api(self, site: dict, username: str) -> Profile:
        api_url = (
            "https://api.juejin.cn/user_api/v1/user/get"
            f"?user_id={urllib.request.quote(username)}"
        )
        base_profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "掘金"),
            url=f"https://juejin.cn/user/{username}",
            username=username,
        )

        try:
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            if data.get("err_no") != 0 or not data.get("data"):
                return base_profile

            user_data = data["data"]
            extra = {}
            if user_data.get("job_title"):
                extra["job_title"] = user_data["job_title"]
            if user_data.get("company"):
                extra["company"] = user_data["company"]

            return Profile(
                site_id=self.site_id,
                site_name=site.get("name", "掘金"),
                url=f"https://juejin.cn/user/{username}",
                username=username,
                display_name=user_data.get("user_name"),
                bio=user_data.get("description") or None,
                avatar_url=user_data.get("avatar_large"),
                extra=extra if extra else {},
            )
        except (OSError, json.JSONDecodeError) as e:
            _api_logger.warning(f"juejin_api_failed username={username} error={e}")
            return base_profile

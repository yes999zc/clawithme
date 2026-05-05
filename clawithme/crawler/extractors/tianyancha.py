"""Tianyancha (天眼查) extractor — requires API token.

API: http://open.api.tianyancha.com/services/v4/open/allCompanys
     ?hid={person_id}&name={company_name}&humanName={person_name}&cid={company_id}

Auth: Authorization header with token from open.tianyancha.com (requires registration)
Price: ¥6/call
Docs: https://open.tianyancha.com/ → 人员相关 → 人员所有公司 (接口ID 450)

When no token is configured, this extractor returns Profile.empty() with
a helpful message in the docstring.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor

logger = logging.getLogger(__name__)

# Read token from env var — set via TIANYANCHA_TOKEN
_TOKEN = os.environ.get("TIANYANCHA_TOKEN", "")


class TianyanchaExtractor(ProfileExtractor):
    """Search 天眼查 for companies associated with a person.

    Requires TIANYANCHA_TOKEN env var to be set (register at open.tianyancha.com).
    Without token, returns empty profile with a note in the docstring.

    API returns: person's companies as legal rep, shareholder, executive.
    Key fields in response: company name, role, capital, status, registration date.
    """

    site_id = "tianyancha"

    def can_handle(self, site_def: dict) -> bool:
        return site_def.get("id") == "tianyancha"

    def extract(self, site_def: dict, username: str) -> Profile:
        """Query 天眼查 for person's company affiliations.

        username is treated as a person name (Chinese characters supported).
        Returns empty profile if no token configured or API fails.
        """
        base_profile = Profile(
            site_id=self.site_id,
            site_name="天眼查",
            url=f"https://www.tianyancha.com/search?key={urllib.request.quote(username)}",
            username=username,
        )

        if not _TOKEN:
            logger.debug("tianyancha_no_token")
            return base_profile

        # Stage 1: search for person to get hid
        # TODO: integrate search API endpoint when available
        # open.tianyancha.com → 搜索 (1 API)
        # This would resolve a person name → hid

        # Stage 2: query allCompanys with hid
        # api_url = (
        #     "http://open.api.tianyancha.com/services/v4/open/allCompanys"
        #     f"?humanName={urllib.request.quote(username)}"
        # )
        # req = urllib.request.Request(api_url, headers={
        #     "Authorization": _TOKEN,
        #     "User-Agent": "clawithme/1.0",
        # })
        try:
            # Placeholder: API integration requires paid token
            return base_profile
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"tianyancha_parse_failed humanName={username} error={e}")
            return base_profile

    @staticmethod
    def is_configured() -> bool:
        """Return True if TIANYANCHA_TOKEN is set and non-empty."""
        return bool(_TOKEN.strip())

"""YouTube channel extractor — dynamic fetch via Playwright.

URL: https://www.youtube.com/@{username}/about
YouTube About pages now require JS rendering. Static HTML returns empty shell.
We use DynamicFetcher (Playwright) and parse og:meta tags + JSON-LD.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import parse_count
from clawithme.logging import get_logger

logger = get_logger()


class YoutubeExtractor(ProfileExtractor):
    """Extract public channel data from YouTube (dynamic fetch)."""

    site_id = "youtube"
    requires_dynamic = True

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.youtube.com/@{quote(username)}/about"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "YouTube"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=20000)
        try:
            response = client.fetch_dynamic(url)
            if response is None or response.status != 200:
                return profile

            html = str(response.html_content) if response.html_content else ""
            if not html or len(html) < 5000:
                return profile

            # Extract from JSON-LD
            _extract_jsonld(html, profile)

            # Fallback: og:title
            if not profile.display_name:
                m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
                if m:
                    profile.display_name = m.group(1)

            # Avatar from og:image
            if not profile.avatar_url:
                m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
                if m:
                    src = m.group(1)
                    if not src.startswith("data:"):
                        profile.avatar_url = src

            # Bio from og:description
            if not profile.bio:
                m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
                if m:
                    desc = m.group(1)
                    if desc:
                        profile.bio = desc

            # Subscriber count from JSON-LD or inline data
            if profile.follower_count is None:
                m = re.search(r'"subscriberCount"\s*:\s*"([^"]+)"', html)
                if m:
                    profile.follower_count = parse_count(m.group(1))

        finally:
            client.close()

        return profile


def _extract_jsonld(html: str, profile: Profile) -> None:
    """Extract channel data from embedded JSON-LD."""
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    ):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                if not profile.display_name:
                    profile.display_name = data.get("name") or None
                if not profile.bio:
                    profile.bio = data.get("description") or None
        except (json.JSONDecodeError, AttributeError):
            continue

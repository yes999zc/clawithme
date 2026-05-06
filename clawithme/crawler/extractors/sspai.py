"""Sspai (少数派) profile extractor — requires dynamic fetch (SPA).

URL: https://sspai.com/u/{username}/
Sspai is a SPA — static HTML is a 2.8KB shell identical for all users.
Requires Playwright rendering to get the actual profile content.
"""

from __future__ import annotations

import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class SspaiExtractor(ProfileExtractor):
    """Extract public profile data from 少数派 (Sspai)."""

    site_id = "sspai"
    requires_dynamic = True

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://sspai.com/u/{username}/"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "少数派"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=20000)
        try:
            response = client.fetch_dynamic(url)
            if response is None or response.status != 200:
                return profile

            html = response.text or ""
            if not html or len(html) < 5000:
                # Too small — likely JS not rendered or redirect to /whoops
                return profile

            # Sspai embeds user data in <script> with window.__NUXT__ or __INITIAL_STATE__
            profile.display_name = _extract_name(html)
            profile.avatar_url = _extract_avatar(html)
            profile.bio = _extract_bio(html)

        finally:
            client.close()

        return profile


def _extract_name(html: str) -> str | None:
    """Extract display name from sspai HTML."""
    # Try __NUXT__ state (Nuxt.js app)
    m = re.search(r'"nickname"\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1)
    # Fallback: page title
    m = re.search(r'<title>([^<]+)\s*-\s*少数派', html)
    if m:
        return m.group(1).strip()
    # Fallback: og:title
    m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if m:
        return m.group(1)
    return None


def _extract_avatar(html: str) -> str | None:
    """Extract avatar URL from sspai HTML."""
    m = re.search(r'"avatar"\s*:\s*"([^"]+)"', html)
    if m:
        src = m.group(1)
        if src.startswith("//"):
            src = "https:" + src
        return src
    m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    if m:
        return m.group(1)
    return None


def _extract_bio(html: str) -> str | None:
    """Extract bio/description from sspai HTML."""
    m = re.search(r'"signature"\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1) or None
    m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
    if m:
        return m.group(1)
    return None

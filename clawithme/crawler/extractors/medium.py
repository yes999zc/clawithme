"""Medium profile extractor — RSS feed primary, CSS fallback.

PRIMARY: Parse RSS feed at https://medium.com/feed/@username
RSS <title> contains author display name, <description> has bio.

FALLBACK: CSS selectors on https://medium.com/@{username} profile page.
"""

from __future__ import annotations

import logging
import urllib.request
import xml.etree.ElementTree as ET

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text

logger = logging.getLogger(__name__)


class MediumExtractor(ProfileExtractor):
    """Extract profile data from Medium (RSS feed + CSS fallback)."""

    site_id = "medium"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://medium.com/@{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Medium"),
            url=url,
            username=username,
        )

        # PRIMARY: Try RSS feed
        rss_result = _try_rss(profile, username)
        if rss_result is not None:
            return rss_result

        # FALLBACK: Try CSS on profile page
        return _try_css(profile, username, site)


def _try_rss(profile: Profile, username: str) -> Profile | None:
    """Try to extract profile data from Medium RSS feed. Returns None on failure."""
    rss_url = f"https://medium.com/feed/@{username}"
    req = urllib.request.Request(rss_url, headers={"User-Agent": "clawithme/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_text = resp.read().decode("utf-8", errors="replace")

        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return None

        title = channel.findtext("title", "").strip()
        description = channel.findtext("description", "").strip()

        if title:
            # Strip trailing " – Medium" suffix
            for suffix in (" – Medium", " - Medium", " — Medium"):
                if title.endswith(suffix):
                    title = title[: -len(suffix)]
                    break
            profile.display_name = title

        if description:
            profile.bio = description

        return profile
    except (OSError, ET.ParseError, UnicodeDecodeError) as e:
        logger.debug(f"medium_rss_failed username={username} error={e}")
        return None


def _try_css(profile: Profile, username: str, site: dict) -> Profile:
    """Fallback: extract profile data from static HTML profile page."""
    url = f"https://medium.com/@{username}"
    client = CrawlerClient(timeout_ms=15000)
    try:
        response = client.fetch_static(url)
        if response is None or response.status != 200:
            return profile

        page_text = response.text

        # Handle "PAGE NOT FOUND" / private accounts
        if "PAGE NOT FOUND" in page_text or "Member-only" in page_text:
            return profile

        # Display name
        name = first_text(response, [
            "meta[property=\"og:title\"]",
            "h1",
            "meta[name=\"title\"]",
        ])
        if name:
            profile.display_name = name

        # Bio
        bio = first_text(response, [
            "meta[name=\"description\"]",
            "meta[property=\"og:description\"]",
            "h2",
        ])
        if bio:
            profile.bio = bio

        # Avatar
        for sel in ["img[class*=\"avatar\"]", "img[alt*=\"avatar\"]",
                     "img[src*=\"cdn-images\"]"]:
            imgs = response.css(sel)
            if imgs:
                src = imgs[0].attrib.get("src", "")
                if src and not src.startswith("data:"):
                    profile.avatar_url = src
                    break

    finally:
        client.close()

    return profile

"""YouTube channel extractor — static HTML from channel About page.

YouTube About pages (/about) include server-rendered metadata and
JSON-LD structured data in the initial HTML, before JS hydration.
"""

from __future__ import annotations

import json
from urllib.parse import quote

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class YoutubeExtractor(ProfileExtractor):
    """Extract public channel data from YouTube About page."""

    site_id = "youtube"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.youtube.com/@{quote(username)}/about"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "YouTube"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            page_text = response.text

            # Handle "This channel doesn't exist" page
            if "This channel doesn" in page_text or "channel does not exist" in page_text.lower():
                return profile

            # Try JSON-LD structured data first (most reliable)
            profile = _extract_jsonld(response, profile)

            # Fall back to CSS selectors if JSON-LD didn't yield display_name
            if not profile.display_name:
                profile = _extract_css(response, profile, page_text)

            logger.debug("youtube_extracted", username=username, display_name=profile.display_name)
        finally:
            client.close()

        return profile


def _extract_jsonld(response, profile: Profile) -> Profile:
    """Extract channel data from embedded JSON-LD/structured data."""
    for script in response.css("script[type=\"application/ld+json\"]"):
        try:
            data = json.loads(script.text)
            if isinstance(data, dict):
                name = data.get("name", "")
                if name:
                    profile.display_name = name
                desc = data.get("description", "")
                if desc:
                    profile.bio = desc
            break
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return profile


def _extract_css(response, profile: Profile, page_text: str) -> Profile:
    """Extract channel data from CSS selectors on the About page."""
    # Display name
    name = first_text(response, [
        "meta[property=\"og:title\"]",
        "meta[name=\"title\"]",
        "yt-formatted-string[class*=\"title\"]",
        "#channel-name",
    ])
    if name:
        profile.display_name = name

    # Description
    desc = first_text(response, [
        "meta[property=\"og:description\"]",
        "meta[name=\"description\"]",
        "#description",
    ])
    if desc:
        profile.bio = desc

    # Subscriber count — look for "subscribers" text patterns
    sub_sel = first_text(response, [
        "yt-formatted-string#subscriber-count",
        "#subscriber-count",
        "[class*=\"subscriber\"]",
    ])
    if sub_sel:
        parsed = parse_count(sub_sel)
        if parsed is not None:
            profile.follower_count = parsed

    # Join date — often in the about section
    join_sel = first_text(response, [
        "#details-container yt-formatted-string",
        "[class*=\"joined-date\"]",
        "[class*=\"about-metadata\"]",
    ])
    if join_sel:
        profile.joined_date = join_sel

    # Avatar
    for sel in ["img[class*=\"channel\"]", "img[class*=\"avatar\"]",
                 "img[id*=\"avatar\"]", "img[alt*=\"avatar\"]"]:
        imgs = response.css(sel)
        if imgs:
            src = imgs[0].attrib.get("src", "")
            if src and not src.startswith("data:"):
                profile.avatar_url = src
                break

    return profile

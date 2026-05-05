"""Dribbble profile extractor — static HTML.

URL: https://dribbble.com/{username}
Dribbble profiles are server-rendered.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class DribbbleExtractor(ProfileExtractor):
    """Extract public profile data from Dribbble."""

    site_id = "dribbble"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://dribbble.com/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Dribbble"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Display name
            name = first_text(response, [
                ".masthead-profile-name",
                "h1[class*=\"name\"]",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Bio (often JS-rendered, fallback to meta description)
            bio = first_text(response, [
                "[class*=\"bio\"]",
                "meta[name=\"description\"]",
            ])
            if bio:
                profile.bio = bio

            # Avatar
            for sel in ["img.profile-avatar", ".profile-avatar img", "img[class*=\"avatar\"]"]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Location
            location = first_text(response, [
                ".masthead-profile-locality",
                "[class*=\"locality\"]",
                "span[class*=\"location\"]",
            ])
            if location:
                profile.location = location

            # Followers (when JS-rendered, may not be available in static HTML)
            follower_text = first_text(response, [
                "[class*=\"followers\"] .count",
                "[class*=\"follower\"] strong",
            ])
            if follower_text:
                profile.follower_count = parse_count(follower_text)

            # Following
            following_text = first_text(response, [
                "[class*=\"following\"] .count",
            ])
            if following_text:
                profile.following_count = parse_count(following_text)

        finally:
            client.close()

        return profile

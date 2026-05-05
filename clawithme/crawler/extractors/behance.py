"""Behance profile extractor — static HTML.

URL: https://www.behance.net/{username}
Behance is client-rendered in some sections; basic profile info may still appear
in static HTML or <meta> tags.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class BehanceExtractor(ProfileExtractor):
    """Extract public profile data from Behance."""

    site_id = "behance"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.behance.net/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Behance"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Display name from <title> fallback
            name = first_text(response, [
                "[class*=\"ProfileHeader\"] [class*=\"name\"]",
                "[class*=\"profile\"] [class*=\"display-name\"]",
                "[class*=\"user\"] [class*=\"fullName\"]",
            ])
            if name:
                profile.display_name = name

            # Bio
            bio = first_text(response, [
                "[class*=\"ProfileHeader\"] [class*=\"bio\"]",
                "[class*=\"profile\"] [class*=\"bio\"]",
                "[class*=\"user\"] [class*=\"description\"]",
            ])
            if bio:
                profile.bio = bio

            # Avatar — Behance uses OG image / structured meta
            for sel in [
                "img[class*=\"Avatar\"]",
                "[class*=\"avatar\"] img",
                "meta[property=\"og:image\"]",
            ]:
                imgs = response.css(sel)
                if imgs:
                    if sel.startswith("meta"):
                        src = imgs[0].attrib.get("content", "")
                    else:
                        src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Location
            location = first_text(response, [
                "[class*=\"location\"]",
                "[class*=\"Location\"]",
            ])
            if location:
                profile.location = location

        finally:
            client.close()

        return profile

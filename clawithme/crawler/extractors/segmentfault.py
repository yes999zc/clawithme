"""SegmentFault profile extractor — static HTML.

URL: https://segmentfault.com/u/{username}
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class SegmentfaultExtractor(ProfileExtractor):
    """Extract public profile data from SegmentFault."""

    site_id = "segmentfault"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://segmentfault.com/u/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "SegmentFault"),
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
                ".profile__name",
                ".user-card__name",
                "h1.user-name",
            ])
            if name:
                profile.display_name = name

            # Bio / description
            bio = first_text(response, [
                ".profile__description",
                ".user-intro",
                ".user-description",
            ])
            if bio:
                profile.bio = bio

            # Avatar
            for sel in ["img.avatar", ".profile__avatar img", ".user-card__avatar img"]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            # Location
            location = first_text(response, [
                ".profile__location",
                "span[class*=\"location\"]",
            ])
            if location:
                profile.location = location

        finally:
            client.close()

        return profile

"""Steam profile extractor — static HTML from steamcommunity.com.

Steam profiles are server-rendered HTML with persona_name, profile_summary, etc.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class SteamExtractor(ProfileExtractor):
    """Extract public profile data from Steam."""

    site_id = "steam"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://steamcommunity.com/id/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Steam"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Handle "The specified profile could not be found"
            if "The specified profile could not be found" in response.text:
                return profile

            # Display name from .persona_name
            name = first_text(response, [".persona_name", ".personaNameText"])
            if name:
                profile.display_name = name

            # Bio from .profile_summary
            bio = first_text(response, [".profile_summary"])
            if bio:
                profile.bio = bio

            # Location from .profile_flag
            location = first_text(response, [".profile_flag"])
            if location:
                profile.location = location

            logger.debug("steam_extracted", username=username, display_name=profile.display_name)
        finally:
            client.close()

        return profile

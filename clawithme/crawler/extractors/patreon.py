"""Patreon profile extractor — static HTML.

URL: https://www.patreon.com/{username}
NOTE: Patreon typically requires authentication or shows a login wall.
Static fetch may return limited data or a signup page.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class PatreonExtractor(ProfileExtractor):
    """Extract public profile data from Patreon (login wall expected)."""

    site_id = "patreon"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.patreon.com/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Patreon"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Check for login wall (page contains signup/login keywords)
            body_text = (response.text or "").lower()
            if "log in" in body_text and ("sign up" in body_text or "join" in body_text):
                logger.info("patreon_login_wall", extra={"username": username})
                return profile

            # Display name
            name = first_text(response, [
                "[class*=\"creator\"] [class*=\"name\"]",
                "[class*=\"profile\"] [class*=\"displayName\"]",
                "h1[class*=\"name\"]",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Bio
            bio = first_text(response, [
                "[class*=\"creator\"] [class*=\"tagline\"]",
                "[class*=\"profile\"] [class*=\"bio\"]",
                "[class*=\"description\"]",
            ])
            if bio:
                profile.bio = bio

            # Avatar
            for sel in [
                "img[class*=\"avatar\"]",
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

        finally:
            client.close()

        return profile

"""Reddit profile extractor — static HTML from www.reddit.com.

Reddit renders profile pages with server-rendered shell content.
Karma/cake day data may require JS rendering — extracted when available.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class RedditExtractor(ProfileExtractor):
    """Extract public profile data from Reddit."""

    site_id = "reddit"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.reddit.com/user/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Reddit"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            page_text = response.text

            # Handle "page not found" / "Sorry, nobody" → empty profile
            if "Sorry, nobody" in page_text or "page not found" in page_text.lower():
                return profile

            # Display name — Reddit server-renders the username in h1
            name = first_text(response, [
                "h1",
                "span[class*=\"username\"]",
                "meta[property=\"og:title\"]",
            ])
            if name:
                profile.display_name = name

            # Karma count — may not be in static HTML, try fallback selectors
            karma_text = first_text(response, [
                "span[class*=\"karma\"]",
                "[class*=\"karma\"]",
            ])
            if karma_text:
                profile.follower_count = parse_count(karma_text)

            # Cake day — try time elements with datetime attribute
            cake_day = first_text(response, [
                "time[datetime]",
                "a[href*=\"cake\"]",
            ])
            if cake_day:
                profile.joined_date = cake_day

            # Avatar — try img elements
            for sel in ["img[class*=\"avatar\"]", "img[alt*=\"avatar\"]", "img[alt*=\"profile\"]"]:
                imgs = response.css(sel)
                if imgs:
                    src = imgs[0].attrib.get("src", "")
                    if src and not src.startswith("data:"):
                        profile.avatar_url = src
                        break

            logger.debug("reddit_extracted", username=username, display_name=profile.display_name)
        finally:
            client.close()

        return profile

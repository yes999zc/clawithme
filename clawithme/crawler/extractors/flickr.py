"""Flickr profile extractor — static HTML.

URL: https://www.flickr.com/people/{username}
Flickr profile pages are server-rendered.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class FlickrExtractor(ProfileExtractor):
    """Extract public profile data from Flickr."""

    site_id = "flickr"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        # Flickr supports both /people/{username} and /photos/{username}
        url = f"https://www.flickr.com/people/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Flickr"),
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
                "h1.truncate",
                ".profile-name",
                "h1",
            ])
            if name:
                profile.display_name = name

            # Bio / description
            bio = first_text(response, [
                ".profile-description",
                "[class*=\"description\"]",
            ])
            if bio:
                profile.bio = bio

            # Avatar (may be JS-rendered, fallback to og:image)
            for sel in [
                "img.profile-avatar",
                ".avatar img",
                "img[class*=\"avatar\"]",
                "meta[property=\"og:image\"]",
                "meta[name=\"twitter:image\"]",
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
                ".profile-location",
                "[class*=\"location\"]",
            ])
            if location:
                profile.location = location

            # Followers
            follower_text = first_text(response, [
                "p.followers.truncate.no-shrink",
                "[class*=\"followers\"]",
            ])
            if follower_text:
                profile.follower_count = parse_count(follower_text)

            # Joined date
            joined = first_text(response, [
                "p.metadata-item.joined",
                ".profile-joined",
                "[class*=\"joined\"]",
            ])
            if joined:
                profile.joined_date = joined

        finally:
            client.close()

        return profile

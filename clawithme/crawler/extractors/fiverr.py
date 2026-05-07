"""Fiverr profile extractor — meta tags + JSON-LD.

URL: https://www.fiverr.com/{username}
Extracts: display_name, bio, avatar_url.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class FiverrExtractor(ProfileExtractor):
    site_id = "fiverr"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.fiverr.com/{username}"
        profile = Profile(site_id=self.site_id, site_name="Fiverr", url=url, username=username)
        client = CrawlerClient(timeout_ms=15000)
        try:
            resp = client.fetch_static(url)
            if resp is None or resp.status != 200:
                return profile
            # og:title
            tag = resp.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                profile.display_name = tag[0].attrib["content"].strip()
            # og:image
            tag = resp.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src
            # description → bio
            tag = resp.css("meta[name='description']")
            if tag and tag[0].attrib.get("content"):
                profile.bio = tag[0].attrib["content"].strip()[:500]
        finally:
            client.close()
        return profile

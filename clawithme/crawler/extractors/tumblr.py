"""Tumblr profile extractor — meta tags + JSON-LD.

URL: https://{username}.tumblr.com
Extracts: display_name, bio, avatar_url, post_count.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class TumblrExtractor(ProfileExtractor):
    site_id = "tumblr"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://{username}.tumblr.com"
        profile = Profile(site_id=self.site_id, site_name="Tumblr", url=url, username=username)
        client = CrawlerClient(timeout_ms=15000)
        try:
            resp = client.fetch_static(url)
            if resp is None or resp.status != 200:
                return profile
            # og:title → display_name
            tag = resp.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                profile.display_name = tag[0].attrib["content"].strip()
            # og:image → avatar
            tag = resp.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src
            # og:description → bio
            tag = resp.css("meta[property='og:description']")
            if tag and tag[0].attrib.get("content"):
                profile.bio = tag[0].attrib["content"].strip()[:500]
            # description meta for extra bio
            if not profile.bio:
                tag = resp.css("meta[name='description']")
                if tag and tag[0].attrib.get("content"):
                    profile.bio = tag[0].attrib["content"].strip()[:500]
        finally:
            client.close()
        return profile

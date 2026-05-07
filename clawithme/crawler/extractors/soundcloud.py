"""SoundCloud profile extractor — meta tags + JSON-LD.

URL: https://soundcloud.com/{username}
Extracts: display_name, bio, avatar_url, follower_count.
"""

from __future__ import annotations

import json

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class SoundcloudExtractor(ProfileExtractor):
    site_id = "soundcloud"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://soundcloud.com/{username}"
        profile = Profile(site_id=self.site_id, site_name="SoundCloud", url=url, username=username)
        client = CrawlerClient(timeout_ms=15000)
        try:
            resp = client.fetch_static(url)
            if resp is None or resp.status != 200:
                return profile
            # og:title
            tag = resp.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                profile.display_name = tag[0].attrib["content"].strip()
            # og:image → avatar
            tag = resp.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src
            # description → bio
            tag = resp.css("meta[name='description']")
            if tag and tag[0].attrib.get("content"):
                profile.bio = tag[0].attrib["content"].strip()[:500]
            # JSON-LD for stats
            for script in resp.css("script[type='application/ld+json']"):
                try:
                    data = json.loads(script.text)
                    if isinstance(data, dict):
                        auth = data.get("author", data)
                        if isinstance(auth, dict):
                            fc = auth.get("followerCount")
                            if fc is not None:
                                profile.follower_count = int(fc)
                            break
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        finally:
            client.close()
        return profile

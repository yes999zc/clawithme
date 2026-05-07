"""Instagram profile extractor — static HTML + meta tags + JSON-LD.

URL: https://www.instagram.com/{username}/
Extracts: display_name, bio, avatar_url, follower_count, following_count, post_count.
"""

from __future__ import annotations

import json
import re

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class InstagramExtractor(ProfileExtractor):
    """Extract public profile data from Instagram."""

    site_id = "instagram"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.instagram.com/{username}/"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Instagram"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            page_text = response.text or ""

            # ── Display name from og:title ──
            # "陈丹 (@oadank) • Instagram photos and videos"
            tag = response.css("meta[property='og:title']")
            if tag and tag[0].attrib.get("content"):
                title = tag[0].attrib["content"]
                clean = re.sub(r"\s*[•·]\s*Instagram.*$", "", title).strip()
                clean = re.sub(r"\s*\(@\S+\)\s*", "", clean).strip()
                if clean:
                    profile.display_name = clean

            # ── Avatar from og:image ──
            tag = response.css("meta[property='og:image']")
            if tag and tag[0].attrib.get("content"):
                src = tag[0].attrib["content"]
                if not src.startswith("data:"):
                    profile.avatar_url = src

            # ── Bio from og:description ──
            tag = response.css("meta[property='og:description']")
            if tag and tag[0].attrib.get("content"):
                bio = tag[0].attrib["content"].strip()
                if bio:
                    profile.bio = bio[:500]

            # ── Stats from meta description fallback or inline JSON ──
            # Try JSON-LD first
            for script in response.css("script[type=\"application/ld+json\"]"):
                try:
                    data = json.loads(script.text)
                    if isinstance(data, dict):
                        # Instagram sometimes puts stats in mainEntity
                        me = data.get("mainEntity", data)
                        if isinstance(me, dict):
                            # follower count
                            fc = me.get("followerCount")
                            if fc is not None:
                                profile.follower_count = int(fc)
                    break
                except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
                    continue

            # Try inline JSON in script tags
            if profile.follower_count is None:
                self._extract_inline_json(page_text, profile)

            # ── Post count from meta stats ──
            if profile.post_count is None:
                self._extract_post_count(page_text, profile)

        finally:
            client.close()

        return profile

    @staticmethod
    def _extract_inline_json(text: str, profile: Profile) -> None:
        """Extract follower/following counts from window.__INITIAL_STATE__ or similar."""
        # Try __INITIAL_STATE__
        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                user = data.get("user", {})
                if not user:
                    # Might be nested under a key
                    for key in data:
                        if isinstance(data[key], dict) and "username" in data[key]:
                            user = data[key]
                            break
                if user:
                    fc = user.get("edge_followed_by", {}).get("count")
                    if fc is not None:
                        profile.follower_count = int(fc)
                    fg = user.get("edge_follow", {}).get("count")
                    if fg is not None:
                        profile.following_count = int(fg)
                    pc = user.get("edge_owner_to_timeline_media", {}).get("count")
                    if pc is not None:
                        profile.post_count = int(pc)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            return

        # Fallback: extract from description meta which sometimes has stats
        desc_m = re.search(r'"(\d[\d,]*)\s*(?:Follower|follower|Post|post)"', text)
        if desc_m:
            try:
                count = int(desc_m.group(1).replace(",", ""))
                if "Follower" in desc_m.group(0) or "follower" in desc_m.group(0):
                    profile.follower_count = count
                elif "Post" in desc_m.group(0) or "post" in desc_m.group(0):
                    profile.post_count = count
            except (ValueError, AttributeError):
                pass

    @staticmethod
    def _extract_post_count(text: str, profile: Profile) -> None:
        """Extract post count from the profile page text."""
        m = re.search(r'(\d[\d,]*)\s*[Pp]osts?', text)
        if m:
            try:
                profile.post_count = int(m.group(1).replace(",", ""))
            except (ValueError, AttributeError):
                pass

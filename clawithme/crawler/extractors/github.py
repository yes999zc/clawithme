"""GitHub profile extractor — uses static Fetcher (server-rendered HTML)."""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger

logger = get_logger()


class GithubExtractor(ProfileExtractor):
    """Extract public profile data from GitHub."""

    site_id = "github"
    requires_dynamic = False

    def can_handle(self, site: dict) -> bool:
        return site.get("id") == "github"

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://github.com/{username}"
        profile = Profile(
            site_id="github",
            site_name=site.get("name", "GitHub"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        response = client.fetch_static(url)

        if response.status != 200:
            logger.warning("github_bad_status", username=username, status=response.status)
            return profile

        # Display name
        name = first_text(response, ["span.p-name", ".vcard-fullname"])
        if name:
            profile.display_name = name

        # Bio
        bio = first_text(response, ["div.p-note", ".user-profile-bio"])
        if bio:
            profile.bio = bio

        # Avatar URL
        for sel in ["img.avatar-user", "a[itemprop=\"image\"] img"]:
            imgs = response.css(sel)
            if imgs:
                src = imgs[0].attrib.get("src", "")
                if src and not src.startswith("data:"):
                    profile.avatar_url = src
                    break

        # Location
        location = first_text(response, [
            "li[itemprop=\"homeLocation\"] .p-label",
            "span.p-label[itemprop=\"homeLocation\"]",
        ])
        if location:
            profile.location = location

        # Follower count
        follower_text = first_text(response, [
            "a[href*=\"followers\"] span.text-bold",
            "a[href*=\"followers\"] span",
        ])
        if follower_text:
            profile.follower_count = parse_count(follower_text)

        # Following count
        following_text = first_text(response, [
            "a[href*=\"following\"] span.text-bold",
            "a[href*=\"following\"] span",
        ])
        if following_text:
            profile.following_count = parse_count(following_text)

        logger.info("github_extracted", username=username, display_name=profile.display_name)
        return profile

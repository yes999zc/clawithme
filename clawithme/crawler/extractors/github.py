"""GitHub profile extractor — uses static Fetcher (server-rendered HTML)."""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text, parse_count
from clawithme.logging import get_logger
from clawithme.signals.avatar import compute_phash
from clawithme.signals.extraction import extract_emails

logger = get_logger()


class GithubExtractor(ProfileExtractor):
    """Extract public profile data from GitHub."""

    site_id = "github"
    requires_dynamic = False

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

        if response is None or response.status != 200:
            logger.warning("github_bad_status", username=username,
                          status=getattr(response, "status", None))
            return profile

        # Display name
        name = first_text(response, ["span.p-name", ".vcard-fullname"])
        if name:
            profile.display_name = name

        # Bio
        bio = first_text(response, ["div.p-note", ".user-profile-bio"])
        if bio:
            profile.bio = bio
            # Extract email from bio text
            emails = extract_emails(bio)
            if emails:
                profile.email = emails[0]  # first email found

        # Avatar URL
        for sel in ["img.avatar-user", "a[itemprop=\"image\"] img"]:
            imgs = response.css(sel)
            if imgs:
                src = imgs[0].attrib.get("src", "")
                if src and not src.startswith("data:"):
                    profile.avatar_url = src
                    break

        # Compute perceptual hash from avatar image
        if profile.avatar_url:
            avatar_resp = client.fetch_static(profile.avatar_url)
            if avatar_resp is not None and avatar_resp.status == 200:
                profile.avatar_phash = compute_phash(avatar_resp.body)

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

        logger.debug("github_extracted", username=username, display_name=profile.display_name)
        return profile

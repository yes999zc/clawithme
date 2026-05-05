"""LinkedIn profile extractor — static HTML (limited, JS-rendered heavily).

LinkedIn requires authentication to view full profiles. The static HTML
contains some server-rendered data in meta tags and structured JSON-LD.
When the page renders a login wall, we return an empty Profile gracefully.
"""

from __future__ import annotations

import json
from urllib.parse import quote

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.logging import get_logger

logger = get_logger()


class LinkedinExtractor(ProfileExtractor):
    """Extract public profile data from LinkedIn (best-effort)."""

    site_id = "linkedin"
    requires_dynamic = True

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.linkedin.com/in/{quote(username)}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "LinkedIn"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            page_text = response.text

            # Login wall or restricted page — return empty gracefully
            if "login" in page_text[:2000].lower() or "Sign in" in page_text[:2000]:
                return profile

            # Try structured JSON-LD data first (most reliable)
            profile = _extract_jsonld(response, profile)

            # Fall back to CSS selectors if JSON-LD didn't yield display_name
            if not profile.display_name:
                profile = _extract_css(response, profile)

            logger.debug("linkedin_extracted", username=username, display_name=profile.display_name)
        finally:
            client.close()

        return profile


def _extract_jsonld(response, profile: Profile) -> Profile:
    """Extract profile data from embedded JSON-LD."""
    for script in response.css("script[type=\"application/ld+json\"]"):
        try:
            data = json.loads(script.text)
            if not isinstance(data, dict):
                continue
            # LinkedIn often wraps in @graph
            items = data if isinstance(data.get("items"), list) else None
            if items is None:
                items = [data.get("mainEntity", data)]

            for item in items if isinstance(items, list) else [items]:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", "")
                if name:
                    profile.display_name = name
                desc = item.get("description", "")
                if desc:
                    profile.bio = profile.bio or desc
                # Try nested author/person objects
                for key in ("author", "creator", "person"):
                    nested = item.get(key, {})
                    if isinstance(nested, dict):
                        nname = nested.get("name", "")
                        if nname and not profile.display_name:
                            profile.display_name = nname
                        ndesc = nested.get("description", "")
                        if ndesc and not profile.bio:
                            profile.bio = ndesc
                break
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return profile


def _extract_css(response, profile: Profile) -> Profile:
    """Extract profile data from CSS selectors on the static HTML."""
    # Display name
    name = first_text(response, [
        "h1",
        "meta[property=\"og:title\"]",
        ".text-heading-xlarge",
        "[class*=\"profile-name\"]",
    ])
    if name:
        profile.display_name = name

    # Headline
    headline = first_text(response, [
        ".text-body-medium",
        "[class*=\"headline\"]",
        "meta[name=\"description\"]",
    ])
    if headline:
        profile.bio = headline

    # Location
    location = first_text(response, [
        "[class*=\"location\"]",
        "span[class*=\"bullet\"]",
    ])
    if location:
        profile.location = location

    # Avatar
    for sel in ["img[class*=\"profile-photo\"]", "img[class*=\"avatar\"]",
                 "img[class*=\"pv-top-card\"]"]:
        imgs = response.css(sel)
        if imgs:
            src = imgs[0].attrib.get("src", "")
            if src and not src.startswith("data:"):
                profile.avatar_url = src
                break

    return profile

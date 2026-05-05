"""Hacker News profile extractor — static HTML from news.ycombinator.com.

HN profile pages use a simple table-based layout with key-value rows.
"""

from __future__ import annotations

import contextlib

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class HackernewsExtractor(ProfileExtractor):
    """Extract public profile data from Hacker News."""

    site_id = "hackernews"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://news.ycombinator.com/user?id={username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Hacker News"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Handle "No such user." page
            if "No such user." in response.text:
                return profile

            # HN uses a nested table structure: the profile table is the
            # innermost <table> containing label-value rows like
            #   <tr><td valign="top">user:</td><td>pg</td></tr>
            #   <tr><td valign="top">created:</td><td>...</td></tr>
            #   <tr><td valign="top">karma:</td><td>...</td></tr>
            #   <tr><td valign="top">about:</td><td>...</td></tr>
            rows = response.css("table table tr")
            for row in rows:
                cells = row.css("td")
                if len(cells) >= 2:
                    label = _cell_text(cells[0]).rstrip(":")
                    value = _cell_text(cells[1])
                    if not label or not value:
                        continue

                    if label == "user":
                        profile.display_name = value
                    elif label == "karma":
                        with contextlib.suppress(ValueError):
                            profile.follower_count = int(value.replace(",", ""))
                    elif label == "created":
                        profile.joined_date = value
                    elif label == "about":
                        profile.bio = value

            logger.debug("hn_extracted", username=username, display_name=profile.display_name)
        finally:
            client.close()

        return profile


def _cell_text(cell) -> str:
    """Extract stripped text from a scrapling element."""
    return cell.text.strip() if cell.text else ""

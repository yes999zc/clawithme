"""Telegram profile extractor — static HTML from t.me pages.

Telegram profile pages are simple static HTML with title/extra fields.
"""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.logging import get_logger

logger = get_logger()


class TelegramExtractor(ProfileExtractor):
    """Extract public profile data from Telegram."""

    site_id = "telegram"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://t.me/{username}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Telegram"),
            url=url,
            username=username,
        )

        client = CrawlerClient(timeout_ms=15000)
        try:
            response = client.fetch_static(url)
            if response is None or response.status != 200:
                return profile

            # Handle "If you have Telegram" — non-existent user
            if "If you have Telegram" in response.text:
                return profile

            # Display name from .tgme_page_title
            titles = response.css(".tgme_page_title")
            if titles:
                text = titles[0].text.strip() if titles[0].text else None
                if text:
                    profile.display_name = text

            # Extra info (subscribers/bio) from .tgme_page_extra
            extras = response.css(".tgme_page_extra")
            if extras:
                text = extras[0].text.strip() if extras[0].text else None
                if text:
                    profile.bio = text

            logger.debug("telegram_extracted", username=username, display_name=profile.display_name)
        finally:
            client.close()

        return profile

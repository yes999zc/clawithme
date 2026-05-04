"""Crawler HTTP client — delegates static fetching to engine's HttpClient.

Includes rate limiting, exponential backoff, and User-Agent rotation.
"""

from __future__ import annotations

import random
import time

from scrapling.engines.toolbelt.custom import Response

from clawithme.engine.http_client import HttpClient
from clawithme.logging import get_logger

logger = get_logger()

# Lazy import — Playwright is heavy
_DYNAMIC_AVAILABLE: bool | None = None

# Remove navigator.webdriver flag (standard headless detection vector)
# NOTE: DynamicFetcher init_script expects a file path, not inline code.
# For stealth, extractors can pass page_setup callable via **kwargs.
_STEALTH_INIT_SCRIPT = None  # placeholder — needs file-based approach for Scrapling

# Common User-Agent strings for rotation
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]


def _check_dynamic() -> bool:
    global _DYNAMIC_AVAILABLE
    if _DYNAMIC_AVAILABLE is None:
        try:
            from scrapling import DynamicFetcher  # noqa: F401
            _DYNAMIC_AVAILABLE = True
        except ImportError:
            logger.warning("dynamic_fetcher_unavailable")
            _DYNAMIC_AVAILABLE = False
    return _DYNAMIC_AVAILABLE


def random_user_agent() -> str:
    """Return a random User-Agent string from the rotation pool."""
    return random.choice(_USER_AGENTS)


# Module-level — shared across all CrawlerClient instances
_last_request_at: float = 0.0


class CrawlerClient:
    """HTTP client for profile extraction with rate limiting and UA rotation.

    Delegates static fetching to engine's HttpClient.
    Adds DynamicFetcher for JS-rendered pages (lazy init).

    Rate limiting is global — all CrawlerClient instances share
    a single inter-request delay timer to prevent burst patterns.
    """

    def __init__(
        self,
        timeout_ms: int = 30000,
        min_delay_ms: int = 200,
        max_retries: int = 2,
        backoff_base_ms: int = 1000,
    ):
        self._timeout_ms = timeout_ms
        self._min_delay_ms = min_delay_ms
        self._max_retries = max_retries
        self._backoff_base_ms = backoff_base_ms
        self._http: HttpClient | None = None
        self._dynamic = None  # DynamicFetcher, lazy

    # ── Rate limiting ────────────────────────────────────────

    def _wait_if_needed(self):
        """Enforce minimum delay between requests (global, across instances)."""
        global _last_request_at
        elapsed = (time.monotonic() - _last_request_at) * 1000
        if elapsed < self._min_delay_ms:
            time.sleep((self._min_delay_ms - elapsed) / 1000)
        _last_request_at = time.monotonic()

    # ── HttpClient access ────────────────────────────────────

    @property
    def http(self) -> HttpClient:
        if self._http is None:
            self._http = HttpClient(timeout_ms=self._timeout_ms)
        return self._http

    @property
    def dynamic(self):
        if not _check_dynamic():
            return None
        if self._dynamic is None:
            from scrapling import DynamicFetcher
            self._dynamic = DynamicFetcher()
        return self._dynamic

    # ── Fetch methods ────────────────────────────────────────

    def fetch_static(self, url: str) -> Response | None:
        """Fetch a page using static Fetcher, with rate limiting + backoff.

        Returns None if all retries are exhausted.
        """
        self._wait_if_needed()

        headers = {"User-Agent": random_user_agent()}

        for attempt in range(self._max_retries + 1):
            try:
                return self.http.static.get(url, headers=headers)
            except (OSError, TimeoutError):
                if attempt < self._max_retries:
                    backoff = self._backoff_base_ms * (2 ** attempt) / 1000
                    logger.debug(
                        "fetch_retry", url=url, attempt=attempt + 1,
                        backoff_s=backoff,
                    )
                    time.sleep(backoff)

        logger.error("fetch_static_exhausted", url=url, retries=self._max_retries)
        return None

    def fetch_dynamic(
        self,
        url: str,
        *,
        wait_selector: str | None = None,
        disable_resources: bool = True,
        block_ads: bool = True,
        headless: bool = True,
        **kwargs,
    ) -> Response | None:
        """Fetch using DynamicFetcher, with rate limiting + backoff.

        Returns None if DynamicFetcher is unavailable or all retries are exhausted.
        """
        self._wait_if_needed()

        df = self.dynamic
        if df is None:
            logger.error("dynamic_fetcher_unavailable_for_url", url=url)
            return None

        for attempt in range(self._max_retries + 1):
            try:
                fetch_kwargs = dict(
                    timeout=self._timeout_ms,
                    useragent=random_user_agent(),
                    headless=headless,
                    disable_resources=disable_resources,
                    block_ads=block_ads,
                    wait_selector=wait_selector,
                    **kwargs,
                )
                if _STEALTH_INIT_SCRIPT is not None:
                    fetch_kwargs["init_script"] = _STEALTH_INIT_SCRIPT
                return df.fetch(url, **fetch_kwargs)
            except (OSError, TimeoutError):
                if attempt < self._max_retries:
                    backoff = self._backoff_base_ms * (2 ** attempt) / 1000
                    logger.debug(
                        "fetch_dynamic_retry", url=url,
                        attempt=attempt + 1, backoff_s=backoff,
                    )
                    time.sleep(backoff)

        logger.error("fetch_dynamic_exhausted", url=url, retries=self._max_retries)
        return None

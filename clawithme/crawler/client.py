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


class CrawlerClient:
    """HTTP client for profile extraction with rate limiting and UA rotation.

    Delegates static fetching to engine's HttpClient.
    Adds DynamicFetcher for JS-rendered pages (lazy init).
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
        self._last_request_at: float = 0.0
        self._http: HttpClient | None = None
        self._dynamic = None  # DynamicFetcher, lazy

    # ── Rate limiting ────────────────────────────────────────

    def _wait_if_needed(self):
        """Enforce minimum delay between requests."""
        elapsed = (time.monotonic() - self._last_request_at) * 1000
        if elapsed < self._min_delay_ms:
            time.sleep((self._min_delay_ms - elapsed) / 1000)
        self._last_request_at = time.monotonic()

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

    def fetch_static(self, url: str) -> Response:
        """Fetch a page using static Fetcher, with rate limiting + backoff."""
        self._wait_if_needed()

        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                return self.http.static.get(url)
            except (OSError, TimeoutError) as e:
                last_error = e
                if attempt < self._max_retries:
                    backoff = self._backoff_base_ms * (2 ** attempt) / 1000
                    logger.debug(
                        "fetch_retry", url=url, attempt=attempt + 1,
                        backoff_s=backoff,
                    )
                    time.sleep(backoff)

        raise last_error  # type: ignore[misc]

    def fetch_dynamic(
        self,
        url: str,
        *,
        wait_selector: str | None = None,
        disable_resources: bool = True,
        block_ads: bool = True,
        **kwargs,
    ) -> Response | None:
        """Fetch using DynamicFetcher, with rate limiting + backoff."""
        self._wait_if_needed()

        df = self.dynamic
        if df is None:
            logger.error("dynamic_fetcher_unavailable_for_url", url=url)
            return None

        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                return df.fetch(
                    url,
                    timeout=self._timeout_ms,
                    disable_resources=disable_resources,
                    block_ads=block_ads,
                    wait_selector=wait_selector,
                    **kwargs,
                )
            except (OSError, TimeoutError) as e:
                last_error = e
                if attempt < self._max_retries:
                    backoff = self._backoff_base_ms * (2 ** attempt) / 1000
                    logger.debug(
                        "fetch_dynamic_retry", url=url,
                        attempt=attempt + 1, backoff_s=backoff,
                    )
                    time.sleep(backoff)

        raise last_error  # type: ignore[misc]

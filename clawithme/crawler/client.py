"""Crawler HTTP client — delegates static fetching to engine's HttpClient."""

from __future__ import annotations

from scrapling.engines.toolbelt.custom import Response

from clawithme.engine.http_client import HttpClient
from clawithme.logging import get_logger

logger = get_logger()

# Lazy import — Playwright is heavy
_DYNAMIC_AVAILABLE: bool | None = None


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


class CrawlerClient:
    """HTTP client for profile extraction.

    Delegates static fetching to engine's HttpClient (single Scrapling Fetcher instance).
    Adds DynamicFetcher support for JS-rendered pages (lazy init).

    Returns raw Scrapling Response objects — extractors use .css() selectors directly.
    This is a known coupling; future work may abstract to a ParsedResponse wrapper.
    """

    def __init__(self, timeout_ms: int = 30000):
        self._timeout_ms = timeout_ms
        self._http: HttpClient | None = None
        self._dynamic = None  # DynamicFetcher, lazy

    @property
    def http(self) -> HttpClient:
        """Get or create the shared HttpClient (delegates to engine layer)."""
        if self._http is None:
            self._http = HttpClient(timeout_ms=self._timeout_ms)
        return self._http

    @property
    def dynamic(self):
        """Lazy DynamicFetcher. Returns None if Playwright unavailable."""
        if not _check_dynamic():
            return None
        if self._dynamic is None:
            from scrapling import DynamicFetcher
            self._dynamic = DynamicFetcher()
        return self._dynamic

    def fetch_static(self, url: str) -> Response:
        """Fetch a page using static Fetcher (no JS rendering).

        Returns raw Scrapling Response for CSS selector access.
        """
        return self.http.static.get(url)

    def fetch_dynamic(
        self,
        url: str,
        *,
        wait_selector: str | None = None,
        disable_resources: bool = True,
        block_ads: bool = True,
        **kwargs,
    ) -> Response | None:
        """Fetch a page using DynamicFetcher (Playwright Chromium).

        Returns None if DynamicFetcher is unavailable.
        """
        df = self.dynamic
        if df is None:
            logger.error("dynamic_fetcher_unavailable_for_url", url=url)
            return None

        return df.fetch(
            url,
            timeout=self._timeout_ms,
            disable_resources=disable_resources,
            block_ads=block_ads,
            wait_selector=wait_selector,
            **kwargs,
        )
